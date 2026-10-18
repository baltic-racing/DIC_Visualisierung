"""Selected AT90CAN registers for the actual canlib.c, not a replacement decoder.

Reference: Microchip doc7679, sections 19.5, 19.10.17, 19.11.1/2.
RX/TX completion disables CANEN, leaves CONMOB; rewriting CONMOB rearms.
"""
import re
from . import firmware
REGISTERS = r'''
#define RXOK 5
#define TXOK 6
#define DLCW 7
#define CONMOB1 7
#define CONMOB0 6
#define DLC3 3
#define AINC 3
#define RTRTAG 2
#define ENASTB 1
static uint8_t CANGCON,CANGIE,CANBT1,CANBT2,CANBT3;
struct PREVIEW_MOB {uint8_t status,control,tag[4],mask[4],data[8],enabled;};
static struct PREVIEW_MOB preview_mobs[15];
static struct PREVIEW_MOB *preview_mob(void) {
    unsigned n=CANPAGE>>4;if(n>=15){fputs("Ungueltiger MOb\n",stderr);exit(71);}return &preview_mobs[n];
}
#define CANSTMOB (preview_mob()->status)
#define CANIDT1 (preview_mob()->tag[0])
#define CANIDT2 (preview_mob()->tag[1])
#define CANIDT3 (preview_mob()->tag[2])
#define CANIDT4 (preview_mob()->tag[3])
#define CANIDM1 (preview_mob()->mask[0])
#define CANIDM2 (preview_mob()->mask[1])
#define CANIDM3 (preview_mob()->mask[2])
#define CANIDM4 (preview_mob()->mask[3])
static unsigned preview_can_enable(unsigned high) {
    unsigned bits=0;for(unsigned i=0;i<(high?7:8);i++)bits|=preview_mobs[i+(high?8:0)].enabled<<i;return bits;
}
#define CANEN1 preview_can_enable(1)
#define CANEN2 preview_can_enable(0)
struct PREVIEW_EVENT {uint64_t seq,time;unsigned kind,id,dlc,mob,reason;uint8_t data[8];};
static struct PREVIEW_EVENT preview_events[256];
static unsigned preview_event_count;
static uint64_t preview_event_seq,preview_event_lost;
static unsigned preview_rx_count,preview_drop_count,preview_tx_count,preview_lcd_count;
static void preview_log(unsigned kind,unsigned id,unsigned dlc,const uint8_t *data,unsigned mob,unsigned reason) {
    if(preview_event_count==256){memmove(preview_events,preview_events+1,255*sizeof *preview_events);preview_event_count--;preview_event_lost++;}
    struct PREVIEW_EVENT *e=&preview_events[preview_event_count++];memset(e,0,sizeof *e);
    e->seq=++preview_event_seq;e->time=preview_elapsed;e->kind=kind;e->id=id;e->dlc=dlc;e->mob=mob;e->reason=reason;
    if(data)memcpy(e->data,data,dlc);
}
static unsigned preview_id(struct PREVIEW_MOB *m) {return (m->tag[0]<<3)|(m->tag[1]>>5);}
static void preview_write_control(uint8_t value) {
    struct PREVIEW_MOB *m=preview_mob();m->control=value;m->enabled=(value>>6)!=0;
    if((value>>6)==1) {
        unsigned dlc=value&15;if(dlc>8)dlc=8;
        memcpy(tx_bytes,m->data,8);preview_tx_count++;
        preview_log(2,preview_id(m),dlc,m->data,CANPAGE>>4,0);
        m->enabled=0;m->status|=1<<TXOK;
    }
}
static uint8_t preview_read_message(void) {
    uint8_t value=preview_mob()->data[CANPAGE&7];
    if(!(CANPAGE&(1<<AINC)))CANPAGE=(CANPAGE&0xf8)|((CANPAGE+1)&7);
    return value;
}
static void preview_write_message(uint8_t value) {
    preview_mob()->data[CANPAGE&7]=value;
    if(!(CANPAGE&(1<<AINC)))CANPAGE=(CANPAGE&0xf8)|((CANPAGE+1)&7);
}
static void preview_arrival(unsigned id,unsigned dlc,const uint8_t *data) {
    if(!(CANGCON&(1<<ENASTB))){preview_drop_count++;preview_log(3,id,dlc,data,15,4);return;}
    unsigned matching=0,configured=0;
    for(unsigned i=0;i<15;i++) {
        struct PREVIEW_MOB *m=&preview_mobs[i];
        if((m->control>>6)<2)continue;
        configured++;
        unsigned mask=(m->mask[0]<<3)|(m->mask[1]>>5);
        if(((preview_id(m)^id)&mask)!=0)continue;
        matching++;
        if(!m->enabled)continue;
        unsigned expected=m->control&15;
        memcpy(m->data,data,dlc); /* bytes beyond DLC retain previous buffer contents */
        m->tag[0]=id>>3;m->tag[1]=(id<<5)&0xe0;m->tag[3]&=~(1<<RTRTAG);
        m->control=(m->control&0xf0)|dlc;
        m->enabled=0;m->status|=(1<<RXOK)|(expected!=dlc?1<<DLCW:0);
        preview_rx_count++;preview_log(1,id,dlc,data,i,0);return;
    }
    preview_drop_count++;
    preview_log(3,id,dlc,data,15,matching?1:configured?2:3);
}
static void preview_emit_events(void) {
    fprintf(preview_protocol,",\"events\":[");
    for(unsigned i=0;i<preview_event_count;i++) {
        struct PREVIEW_EVENT *e=&preview_events[i];
        fprintf(preview_protocol,"%s{\"seq\":%llu,\"at_ms\":%llu,\"kind\":%u,\"can_id\":%u,\"dlc\":%u,\"mob\":%u,\"reason\":%u,\"data\":[",i?",":"",(unsigned long long)e->seq,(unsigned long long)e->time,e->kind,e->id,e->dlc,e->mob,e->reason);
        for(unsigned b=0;b<e->dlc;b++)fprintf(preview_protocol,"%s%u",b?",":"",e->data[b]);
        fprintf(preview_protocol,"]}");
    }
    fprintf(preview_protocol,"],\"event_loss\":%llu,\"counts\":{\"rx\":%u,\"drop\":%u,\"tx\":%u,\"lcd\":%u},\"mobs\":[",(unsigned long long)preview_event_lost,preview_rx_count,preview_drop_count,preview_tx_count,preview_lcd_count);
    for(unsigned i=0;i<15;i++) {
        struct PREVIEW_MOB *m=&preview_mobs[i];
        fprintf(preview_protocol,"%s{\"number\":%u,\"enabled\":%u,\"status\":%u,\"control\":%u,\"id\":%u,\"data\":[",i?",":"",i,m->enabled,m->status,m->control,preview_id(m));
        for(unsigned b=0;b<8;b++)fprintf(preview_protocol,"%s%u",b?",":"",m->data[b]);
        fprintf(preview_protocol,"]}");
    }
    fprintf(preview_protocol,"]");
    preview_event_count=0; /* transport drained, never a hardware receive queue */
}
static uint8_t preview_ddram[128],preview_lcd_address,preview_lcd_cgram,preview_lcd_increment=1,preview_lcd_on;
static void preview_lcd_write(uint8_t data,uint8_t rs) {
    uint8_t bytes[2]={rs,data};preview_lcd_count++;
    preview_log(4,0,2,bytes,0,0);
    if(rs) {
        if(preview_lcd_cgram)glyphs[preview_lcd_address/8][preview_lcd_address%8]=data&31;
        else preview_ddram[preview_lcd_address]=data;
        preview_lcd_address=(preview_lcd_address+(preview_lcd_increment?1:127))&(preview_lcd_cgram?63:127);
    } else if(data&0x80){preview_lcd_cgram=0;preview_lcd_address=data&127;}
    else if(data&0x40){preview_lcd_cgram=1;preview_lcd_address=data&63;}
    else if(data==1){memset(preview_ddram,32,sizeof preview_ddram);preview_lcd_address=0;preview_lcd_cgram=0;}
    else if(data==2){preview_lcd_address=0;preview_lcd_cgram=0;}
    else if((data&0xfc)==4)preview_lcd_increment=!!(data&2);
    else if((data&0xf8)==8)preview_lcd_on=!!(data&4);
}
static void preview_emit_lcd(void) {
    const unsigned addresses[4]={0,0x40,0x14,0x54};
    fprintf(preview_protocol,",\"lcd_hex\":\"");
    for(unsigned r=0;r<4;r++)for(unsigned c=0;c<20;c++)fprintf(preview_protocol,"%02x",preview_lcd_on?preview_ddram[addresses[r]+c]:32);
    fprintf(preview_protocol,"\",\"lcd_address\":%u,\"lcd_on\":%u",preview_lcd_address,preview_lcd_on);
}
'''


def driver(source):
    """Preserve supplied driver branches and reads; hook only register side effects."""
    source=firmware.strip_includes(source)
    source=re.sub(r'\bCANCDMOB\s*=\s*([^;]+);',r'preview_write_control(\1);',source)
    source=re.sub(r'\bCANMSG\s*=\s*([^;]+);',r'preview_write_message(\1);',source)
    source=re.sub(r'\bCANMSG\b','preview_read_message()',source)
    if re.search(r'\bCANCDMOB\b',firmware.uncomment(source)):
        raise ValueError('CAN-Treiber enthält einen neuen CANCDMOB-Zugriff. Registeradapter prüfen.')
    return source
