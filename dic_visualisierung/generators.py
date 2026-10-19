"""Existing input fields encode sender frames; never fill a receive buffer on read."""
import copy


def encode(packet,ident,pages):
    v=packet['values'];data=[0]*8
    def little(offset,value):data[offset:offset+2]=[value&255,(value>>8)&255]
    def big(offset,value):data[offset:offset+2]=[(value>>8)&255,value&255]
    if ident==0x200:
        little(0,v['ts']);little(2,v['current']);little(4,v['soc'])
        data[6]=(v['ams_error']<<7)|(v['imd_error']<<6)|(v['can_ok']<<5)|(v['precharge']<<4)|(v['ts_ready']<<3)
    elif ident==0x201:
        if v['ams_sender']:
            little(0,v['cell_min']);little(2,v['cell_max']);little(4,v['accu_min'])
        little(6,v['accu'])
    elif ident==0x204:data[0]=v['diag']
    elif ident==0x401:little(0,v['front']*10);little(2,v['rear']*10)
    elif ident==0x400:data[7]=v['steering']&255
    elif ident==0x420:little(0,v['cooling'])
    elif ident==0x300:little(0,v['apps1']);little(2,v['apps2'])
    elif ident==0x600:
        little(2,v['lv']);little(4,sum(v['sdc'+str(bit)]<<bit for bit in (15,14,13,12,11,8,7,6)))
        data[6]=v['fan'];data[7]=v['fuse']
    elif ident==0x750:
        data[1]=pages.index(packet['page']);data[2]=v['buttons']&1;data[3]=(v['buttons']>>1)&1
        data[4]=1-((v['buttons']>>2)&1);data[6]=1-((v['buttons']>>3)&1)
    elif ident==0x44a:big(0,v['inv0']);big(2,v['motor0'])  # actual decoder; contradicts ERPM comment
    elif ident==0x453:big(0,v['inv1']);big(2,v['motor1'])
    elif ident==0x797:big(6,v['speed'])
    return data


class Generator:
    def __init__(self,config):
        self.config=copy.deepcopy(config)
        self.next=config['start_ms']
        self.enabled=config.get('enabled',True)
        self.freeze=False
        self.last_counter=None

    def emit(self,stamp,packet,pages,ams_fault=False):
        c=self.config;ident=c['can_id'];v=packet['values']
        period=({0x200:20,0x201:100}.get(ident,10) if v['ams_sender'] else 10) if c.get('_adaptive_ams_period') else c['period_ms']
        self.next+=period
        if not self.enabled:return None
        overridden=any(ident==override_id for override_id,_ in packet['overrides'])
        # 0x204 is a deliberate DIC test extension, absent from the AMS TY26 sender.
        if ident==0x204 and v['ams_sender'] and 'data' not in c and not overridden:
            return None
        if stamp>=500 and ((ident in (0x200,0x201) and v['ams_mode']==2) or (ident==0x797 and v['gps_mode']) or (ident==0x204 and v['diag_mode'])):
            return None
        data=list(c['data']) if 'data' in c else encode(packet,ident,pages)
        if ident==0x200 and v['ams_sender'] and 'data' not in c:
            data[6]&=~(1<<5)  # This AMS firmware does not send CAN_OK.
            data[6]|=int(ams_fault)<<7
        counter=c.get('counter') or (dict(byte=7,start=0 if v['ams_sender'] else 1,step=1) if ident==0x200 and 'data' not in c else None)
        if counter:
            freeze=self.freeze or (ident==0x200 and v['ams_mode']==1)
            if self.last_counter is None:self.last_counter=counter['start']
            elif not freeze:
                self.last_counter=(self.last_counter+counter['step'])&255
                if v['ams_sender'] and ident==0x200 and 'counter' not in c and self.last_counter==255:
                    self.last_counter=0  # CAN_50 skips 255 in the supplied firmware.
            data[counter['byte']]=self.last_counter
        for override_id,raw in packet['overrides']:
            if override_id==ident:data=list(raw)
        return dict(can_id=ident,dlc=len(data),data=data)
