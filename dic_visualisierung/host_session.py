"""C boundary for a resident firmware stack; no coroutine or longjmp emulation.

Only the outer main-loop boundary cooperates. An iteration cannot be interrupted:
the Python watchdog terminates a hung worker instead of resuming invalid state.
"""
import re
from . import firmware
PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#define preview_dup _dup
#define preview_dup2 _dup2
#define preview_fileno _fileno
#define preview_fdopen _fdopen
#else
#include <unistd.h>
#define preview_dup dup
#define preview_dup2 dup2
#define preview_fileno fileno
#define preview_fdopen fdopen
#endif
#define wait preview_wait
#define MOBNB0 4
uint8_t PINA=255, CANPAGE=0, SPCR=0, SPDR=0;
#define SPE 6
#define SPIE 7
#define MSTR 4
#define SPR0 0
#define ISR(vector) void preview_##vector(void)
volatile uint32_t sys_time=0;
volatile uint8_t draw_data=0;
uint32_t sys_time_read(void) {return sys_time;}
static uint64_t preview_elapsed=0;
static unsigned requested_page;
static int preview_inspect=-1;
static uint8_t extender_latch[2]={255,255},tx_bytes[8],glyphs[8][8];
static int glyph_address=-1;
struct RAW_OVERRIDE {unsigned id; uint8_t data[8];};
static struct RAW_OVERRIDE overrides[16];
static unsigned override_count=0;
static FILE *preview_protocol;
void sys_timer_config(void) {}
void sei(void) {}
'''

PROTOTYPE = r'''
static void preview_checkpoint(struct DISPLAY_PAGE **,struct DISPLAY_STATE *,
                              uintptr_t *,unsigned,uint32_t,uint8_t,uint8_t);
'''

ENTRY = r'''
static void preview_emit(struct DISPLAY_PAGE *display,struct DISPLAY_STATE *state,
                         uintptr_t *pages,unsigned count,uint32_t old,uint8_t ten,uint8_t hundred) {
    unsigned active=0;
    for(unsigned i=0;i<count;i++)if((struct DISPLAY_PAGE *)pages[i]==display)active=i;
    fprintf(preview_protocol,"DIC1 {\"time_ms\":%llu,\"sys_time\":%u,\"active_index\":%u,\"rows_hex\":\"",
            (unsigned long long)preview_elapsed,(unsigned)sys_time,active);
    unsigned buffer=preview_inspect>=0?(unsigned)preview_inspect:active;
    struct DISPLAY_PAGE *logical=(struct DISPLAY_PAGE *)pages[buffer];
    for(int r=0;r<4;r++)for(int c=0;c<20;c++)fprintf(preview_protocol,"%02x",logical->data[r][c]);
    fprintf(preview_protocol,"\",\"glyphs_hex\":\"");
    for(int r=0;r<8;r++)for(int c=0;c<8;c++)fprintf(preview_protocol,"%02x",glyphs[r][c]);
    fprintf(preview_protocol,"\",\"outputs\":{\"ams_led\":%u,\"imd_led\":%u,\"left\":%u,\"right\":%u,\"ports\":{\"A\":%u,\"C\":%u,\"D\":%u,\"G\":%u},\"tx\":[",
      !!(PORTD&0x9f),(PORTA>>PA2)&1,(uint8_t)~extender_latch[0],(uint8_t)~extender_latch[1],PORTA,PORTC,PORTD,PORTG);
    for(int i=0;i<8;i++)fprintf(preview_protocol,"%s%u",i?",":"",tx_bytes[i]);
    fprintf(preview_protocol,"]");
#ifdef PREVIEW_HAS_AMS_DIAG
    fprintf(preview_protocol,",\"ams_diagnostic_code\":%u,\"ams_diagnostic_valid\":%u",ams_diagnostic_code,ams_diagnostic_valid);
#endif
    fprintf(preview_protocol,"},\"state\":{\"sys_time_old\":%u,\"time_10ms\":%u,\"time_100ms\":%u,\"display_row\":%u,\"display_column\":%u",
            (unsigned)old,ten,hundred,state->row,state->column);
    PREVIEW_OBSERVERS
    fprintf(preview_protocol,"},\"buffer_index\":%u",buffer);
    preview_emit_events();preview_emit_lcd();
    fprintf(preview_protocol,"}\n");
    fflush(preview_protocol);
}

static long preview_number(char **next) {
    char *token=strtok(NULL," \r\n"),*end;
    if(!token){fputs("Unvollstaendiger Eingabebefehl\n",stderr);exit(71);}
    long value=strtol(token,&end,10);
    if(*end){fputs("Ungueltiger Eingabewert\n",stderr);exit(71);}
    (void)next;
    return value;
}

static void preview_checkpoint(struct DISPLAY_PAGE **active,struct DISPLAY_STATE *state,
 uintptr_t *pages,unsigned count,uint32_t old,uint8_t ten,uint8_t hundred) {
    static unsigned remaining=0;
    static uint32_t delta=1;
    static int started=0,pending=0;
    static long staged[INPUT_COUNT];
    static unsigned staged_page=0,staged_count=0;
    static struct RAW_OVERRIDE staged_raw[16];
    static struct {unsigned id,dlc;uint8_t data[8];} incoming[128];
    static unsigned incoming_count=0;
    if(!started){started=1;preview_emit(*active,state,pages,count,old,ten,hundred);}
    if(remaining){remaining--;if(!remaining)preview_emit(*active,state,pages,count,old,ten,hundred);}
    while(!remaining) {
        char line[8192];
        if(!fgets(line,sizeof line,stdin))exit(0);
        if(!strchr(line,'\n')){fputs("Protokollzeile zu lang\n",stderr);exit(71);}
        if(!strcmp(line,"S\n")){preview_emit(*active,state,pages,count,old,ten,hundred);continue;}
        if(!strcmp(line,"Q\n"))exit(0);
        if(line[0]=='V') {
            int view;char extra;
            if(sscanf(line,"V %d %c",&view,&extra)!=1||view< -1||(view>=0&&(unsigned)view>=count))exit(71);
            preview_inspect=view;preview_emit(*active,state,pages,count,old,ten,hundred);continue;
        }
        if(line[0]=='F'||line[0]=='B') {
            int immediate=line[0]=='B';char *next=NULL;strtok(line," \r\n");
            long n=preview_number(&next);if(n<0||n>128||incoming_count)exit(71);
            for(unsigned i=0;i<(unsigned)n;i++) {
                long id=preview_number(&next),dlc=preview_number(&next);
                if(id<0||id>2047||dlc<0||dlc>8)exit(71);
                incoming[i].id=(unsigned)id;incoming[i].dlc=(unsigned)dlc;
                memset(incoming[i].data,0,8);
                for(unsigned b=0;b<(unsigned)dlc;b++){long v=preview_number(&next);if(v<0||v>255)exit(71);incoming[i].data[b]=(uint8_t)v;}
            }
            if(strtok(NULL," \r\n"))exit(71);
            incoming_count=(unsigned)n;
            if(immediate){for(unsigned i=0;i<incoming_count;i++)preview_arrival(incoming[i].id,incoming[i].dlc,incoming[i].data);incoming_count=0;}
            preview_emit(*active,state,pages,count,old,ten,hundred);continue;
        }
        if(line[0]=='A') {
            unsigned long long ticks=0,width=0;char extra;
            if(sscanf(line,"A %llu %llu %c",&ticks,&width,&extra)!=2||ticks<1||ticks>10000||width<1||width>UINT32_MAX)exit(71);
            remaining=(unsigned)ticks;delta=(uint32_t)width;
        } else if(line[0]=='I') {
            char *next=NULL;
            strtok(line," \r\n");
            long page=preview_number(&next);
            if(page<0||(unsigned)page>=count)exit(71);
            staged_page=(unsigned)page;
            for(unsigned i=0;i<INPUT_COUNT;i++)staged[i]=preview_number(&next);
            long raw_count=preview_number(&next);
            if(raw_count<0||raw_count>16)exit(71);
            staged_count=(unsigned)raw_count;
            for(unsigned i=0;i<staged_count;i++) {
                long id=preview_number(&next);if(id<0||id>2047)exit(71);
                staged_raw[i].id=(unsigned)id;
                for(int b=0;b<8;b++){long v=preview_number(&next);if(v<0||v>255)exit(71);staged_raw[i].data[b]=(uint8_t)v;}
            }
            if(strtok(NULL," \r\n"))exit(71);
            pending=1;preview_emit(*active,state,pages,count,old,ten,hundred);
        } else exit(71);
    }
    /* Deterministic tick: timer ISR, pending input edge, one complete main iteration. */
    preview_elapsed+=delta;
    sys_time=(uint32_t)(sys_time+delta);
    draw_data=(uint8_t)(draw_data+delta);
    if(pending) {
        memcpy(inputs,staged,sizeof inputs);requested_page=staged_page;
        memcpy(overrides,staged_raw,sizeof overrides);override_count=staged_count;
        PINA=255;
        if(input_ts_button)PINA&=~(1<<PA0);
        if(input_r2d_button)PINA&=~(1<<PA1);
        pending=0;
    }
    for(unsigned i=0;i<incoming_count;i++)preview_arrival(incoming[i].id,incoming[i].dlc,incoming[i].data);
    incoming_count=0;
}

int main(int argc,char **argv) {
    int fd=preview_dup(preview_fileno(stdout));
    if(fd<0||preview_dup2(preview_fileno(stderr),preview_fileno(stdout))<0)return 70;
    setvbuf(stdout,NULL,_IONBF,0);
    preview_protocol=preview_fdopen(fd,"w");if(!preview_protocol)return 70;
    setvbuf(preview_protocol,NULL,_IOLBF,0);
    memset(preview_ddram,32,sizeof preview_ddram);
    PREVIEW_INITIAL_VALUES
    /* Compatibility input: initial mode applies once, never on a later I command. */
    if(argc>1)active_mode=selected_mode=(uint8_t)strtoul(argv[1],NULL,10);
    firmware_main();
    fputs("Firmware-Hauptschleife unerwartet beendet\n",stderr);
    return 72;
}
'''


def time_types(source):
    # AVR unsigned long is 32 bits; LP64 macOS long is 64 bits.
    return re.sub(r'\bunsigned\s+long(?=\s+(?:sys_time|sys_time_old|ams_disconnect_timestamp)\b)', 'uint32_t', source)


def instrument_main(source):
    entry = re.search(r'\bint\s+firmware_main\s*\([^)]*\)\s*\{', firmware.uncomment(source))
    if not entry:
        raise ValueError('Sitzungsadapter: firmware_main fehlt.')
    close, _ = firmware.function_end(source, entry.end())
    loops = list(re.finditer(r'\bwhile\s*\(\s*1\s*\)\s*\{', firmware.uncomment(source)[entry.end():close]))
    if len(loops) != 1:
        raise ValueError('Sitzungsadapter erwartet eine äußere while(1)-Hauptschleife. Adapter gezielt anpassen.')
    position = entry.end() + loops[0].end()
    checkpoint = '\npreview_checkpoint(&active_display,&display_state,page_order,NELEMS(page_order),sys_time_old,time_10ms,time_100ms);\n'
    return source[:position] + checkpoint + source[position:]


def entry(sources, fields):
    text = '\n'.join(firmware.uncomment(s) for s in sources.values())
    observers = []
    for name in ('led_test','wait','active_mode','selected_mode','mode_selection_active',
                 'bms_error_active','IMD_LED_ON','imd_error_count','brake_balance_front',
                 'brake_balance_rear','gps_age_ticks','ams_diag_age_ticks','TS_ON','Ready_2_Drive','speed_valid','speed_kmh','APPS1','BPSF','BPSR','bms_max_temp','mcu_temp','motor_temp','last_ams_counter','ams_error_counter1','ams_disconnect_timestamp','SAS_abs'):
        if re.search(r'\b(?:u?int(?:8|16|32)_t|unsigned\s+long)\s+' + name + r'\s*=', text):
            actual = 'preview_wait' if name == 'wait' else name
            observers.append('fprintf(preview_protocol,",\\"'+name+'\\":%u",(unsigned)'+actual+');')
    defaults = '\n'.join('inputs['+str(i)+']='+str(f['default'])+';' for i,f in enumerate(fields))
    return ENTRY.replace('PREVIEW_OBSERVERS','\n'.join(observers)).replace('PREVIEW_INITIAL_VALUES',defaults)
