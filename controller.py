from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0

from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet,udp,tcp
from ryu.lib.packet import ether_types


class Controller(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)

        # out_port = slice_to_port[dpid][in_port]
        #self.mac_to_port = {4:{},5:{}}
        self.mac_to_port = {1:{}}
        self.slice_to_port = {
            1: {3:4,4:3,1:2,2:1,5:0,6:0}
        }
        
        self.end_switches = [4,5]

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # construct flow_mod message and send it.
        mod = parser.OFPFlowMod(
            datapath=datapath,
            match=match,
            cookie=0,
            command=ofproto.OFPFC_ADD,
            idle_timeout=20,
            hard_timeout=120,
            priority=priority,
            flags=ofproto.OFPFF_SEND_FLOW_REM,
            actions=actions,
        )
        datapath.send_msg(mod)

    def _send_package(self, msg, datapath, in_port, actions):
        data = None
        ofproto = datapath.ofproto
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        # self.logger.info("send_msg %s", out)
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        in_port = msg.in_port
        dpid = datapath.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src
        

        # self.logger.info("packet in s%s in_port=%s eth_src=%s eth_dst=%s pkt=%s udp=%s", dpid, in_port, src, dst, pkt, pkt.get_protocol(udp.udp))
        self.logger.info("CONTROLLER packet arrived in s%s (in_port=%s)", dpid, in_port)
        flag = 0
        if pkt.get_protocol(udp.udp) and pkt.get_protocol(udp.udp).dst_port == 5060:
            flag = 1
        if dpid in self.mac_to_port:
            self.mac_to_port[dpid][src] = in_port
            if pkt.get_protocol(udp.udp) and ((pkt.get_protocol(udp.udp).dst_port == 5060)or(pkt.get_protocol(udp.udp).src_port == 5060)):
                self.logger.info("CONTROLLER Pacchetto VOIP")
                
           
                if dst in self.mac_to_port[dpid]:
                    out_port = self.mac_to_port[dpid][dst]
                    self.logger.info("CONTROLLER Invio pacchetto VOIP")
                else:
                    self.logger.info("CONTROLLER Flooding pacchetto VOIP")
                    out_port = ofproto.OFPP_FLOOD
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                if flag == 0:

                    match = datapath.ofproto_parser.OFPMatch(
                        in_port=in_port,
                        dl_dst=dst,
                        dl_src=src,
                        tp_src=5060,
                    )
                else:
                    match = datapath.ofproto_parser.OFPMatch(
                        in_port=in_port,
                        dl_dst=dst,
                        dl_src=src,
                        tp_dst=5060,
                    )

                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)
            
            else:
                self.logger.info("CONTROLLER Pacchetto GENERICO")
                out_port = self.slice_to_port[dpid][in_port]
                if out_port != 0:
                    self.logger.info("CONTROLLER invio GENERICO")
                    actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                    match = datapath.ofproto_parser.OFPMatch(
                        in_port=in_port,
                        dl_dst=dst,
                        dl_src=src,
                        tp_dst=5060,
                    )
                    self.add_flow(datapath, 1, match, actions)
                    self._send_package(msg, datapath, in_port, actions)



        


       