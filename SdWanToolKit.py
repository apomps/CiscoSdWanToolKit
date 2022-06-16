import requests
import urllib3
urllib3.disable_warnings()
import json
from tabulate import tabulate
import time
from datetime import datetime
import os
from threading import Thread
import ipaddress
import re
from jinja2 import Template

vmanage = "10.10.20.90"
base_url = f"https://{vmanage}:8443/"
auth_endpoint = "j_security_check"
login_body = {"j_username": "admin","j_password": "C1sco12345"}
token_endpoint = "dataservice/client/token"

with open(f"{os.getcwd()}/banner_template.j2","r") as banner:
    banner_template = banner.read()
banner_template = Template(banner_template)
with open(f"{os.getcwd()}/menu_template.j2","r") as menu:
    menu_template = menu.read()
menu_template = Template(menu_template)

class SdWan:
    def __init__(self):
        self.name = ""

    def sdwan_login(self):
        sess = requests.session()
        try:
            login_response = sess.post(url=base_url+auth_endpoint,data=login_body, verify=False)
        except Exception as e:
            print("login failed")
            print(e)
            sess.close()
            exit()
            #return None
        else:
            if not login_response.ok or login_response.text:
                print("Login failed. Confirm credentials")
                sess.close()
                exit()
                #return None
            else:
                print("\rLogin succeeded!")
                get_token = sess.get(url=base_url+token_endpoint, verify=False)
                if get_token.status_code == 200:
                    if b'<html>' in get_token.content:
                        print ("Login Token Failed")
                        sess.close()
                        exit()
                        #return None
                    else:
                        print("\rLogin Token succeeded!")
                        sess.headers["X-XSRF-TOKEN"] = get_token.content
                        self.sess = sess
                        return sess

    def get_devices(self):
        startTime = time.time() #DEVICES
        devices = self.sess.get(url=base_url+"dataservice/device", verify=False).json()
        executionTime = (time.time() - startTime) #DEVICESs
        print("Took {0:.2f} seconds to get devices".format(executionTime))
        self.devices = devices
        #return devices

    def get_routing(self):
        all_devices = []
        startTime = time.time() #INTERFACES+ROUTES
        for i in self.devices["data"]:
            routetable = self.sess.get(url=base_url+f"dataservice/device/ip/routetable?{self.filter_vpn}address-family=ipv4&deviceId={i['deviceId']}", verify=False).json()
            interfaces = self.sess.get(url=base_url+f"dataservice/device/interface?{self.filter_vpn}af-type=ipv4&deviceId={i['deviceId']}", verify=False).json()
            all_devices.append({"host-name":i["host-name"],
                  "device-type":i["device-type"],
                  "deviceId":i["deviceId"],
                  "reachability":i["reachability"],
                  "site-id":i["site-id"],
                  "status":i["status"],
                  "state":i["state"],
                  "routetable": routetable["data"],
                  "interfaces": interfaces["data"]})
        executionTime = (time.time() - startTime) #INTERFACES+ROUTES
        print("Took {0:.2f} seconds to get routes and interfaces".format(executionTime))
        self.all_devices = all_devices
        #return all_devices

    def get_best_route(self):
        for i in self.devices["data"]:
            if i["device-type"] == "vsmart":
                self.vsmart = {}
                self.vsmart["stats"] = f"vSmart Controller: {i['host-name']} {i['deviceId']} {i['reachability']} status:{i['status']} state:{i['state']}"
                omp = self.sess.get(url=base_url+f"dataservice/device/omp/routes/received?{self.filter_vpn}deviceId={i['deviceId']}", verify=False).json()
                temp_route = {"prefix":"0.0.0.0/0"}
                for route in omp["data"]:
                    network = ipaddress.ip_network(route["prefix"])
                    if ipaddress.ip_network(self.find_host).subnet_of(network):
                        if ipaddress.ip_network(temp_route["prefix"]).supernet_of(ipaddress.ip_network(route["prefix"])):
                            temp_route = route
                if len(temp_route) > 1:
                    if temp_route["prefix"] == "0.0.0.0/0":
                        self.vsmart["originator-site-id"] = temp_route["site-id"]
                        self.vsmart["omp"] = f'No specific OMP route for {self.find_host}, most likely default route will be used, originated by {temp_route["originator"]}, site-id {temp_route["site-id"]}'
                    else:
                        self.vsmart["originator-site-id"] = temp_route["site-id"]
                        self.vsmart["omp"] = f'Most specific OMP route for {self.find_host} is {temp_route["prefix"]}, originated by {temp_route["originator"]}, site-id {temp_route["site-id"]}'
                else:
                    self.vsmart["originator-site-id"] = ""
                    self.vsmart["omp"] = f'No specific OMP route for {self.find_host}, most likely default route will be used'
                break
    
        matched_routes = {}
        for device in self.all_devices:
            if "routetable" in device.keys():
                for route in device["routetable"]:
                    if re.findall("[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\/[0-9]{1,2}",route["prefix"]):
                        network = ipaddress.ip_network(route["prefix"])
                        if ipaddress.ip_network(self.find_host).subnet_of(network):
                            matched_routes[device["deviceId"]+str(route["vpn-id"])] = {"host-name": device["host-name"],
                                        "deviceId": device["deviceId"],
                                        "site-id": device["site-id"],
                                        "prefix": route["prefix"],
                                        "vpn-id": str(route["vpn-id"]),
                                        }
        self.matched_routes = matched_routes
        #return matched_routes

    def nping(self):
        def run_nping(nping_endpoint,payload,i):
            r = self.sess.post(url=base_url+nping_endpoint, data=json.dumps(payload), verify=False).json()
            nping_results.append({"HOSTNAME": i["host-name"],
            "deviceId": i["deviceId"],
            "site-id": i["site-id"],
            "ROUTE_USED": i["prefix"],
            "VPN": i["vpn-id"],
            "packetsTransmitted": r["packetsTransmitted"],
            "packetsReceived": r["packetsReceived"],
            "lossPercentage": r["lossPercentage"],
            "avgRoundTrip": r["avgRoundTrip"]})

        startTime = time.time() #PING
        nping_results = []
        threads = []
        for i in self.matched_routes.values():
            nping_endpoint = f"dataservice/device/tools/nping/{i['deviceId']}"
            payload = {"host":self.find_host,
                        "vpn": i['vpn-id'],
                       # "source":i['ifname'],
                        "probeType":"icmp"}
            thr = Thread(target=run_nping, args=(nping_endpoint,payload,i,))
            threads.append(thr)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        executionTime = (time.time() - startTime)#PING
        print("Took {0:.2f} seconds to perform nping".format(executionTime))
        return nping_results

    def get_find_host(self):
        find_host = input("What is the IPv4 host?:").strip()
        find_vpn = input("What is the VPN ID?:").strip()
        if re.findall("[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}",find_host):
            if find_vpn.isdigit():
                print(f"Let's try to find {find_host} on VPN {find_vpn}...")
                filter_vpn = f"vpn-id={find_vpn}&"
            else:
                print(f"VPN Id provided is not a digit. Will try to find {find_host} on all possible VPNs")
                filter_vpn = ""
            self.find_host = find_host
            self.find_vpn = find_vpn
            self.filter_vpn = filter_vpn
            #return find_host, find_vpn, filter_vpn
        else:
            print("Does not look like an IPv4 address. Please try again. Bye!")
            exit()

    def sdwan_site_details(self):
        device_interface = "dataservice/device/interface"
        omp_api = "dataservice/device/omp/summary"
        bfd_api = "dataservice/device/bfd/sessions"
        tunnel_api = "dataservice/device/tunnel/statistics"
        all_devices_detail = []
        for device in self.devices["data"]:
            if device["site-id"] == self.vsmart["originator-site-id"]:
                if device["reachability"] == "reachable":
                    interfaces = self.sess.get(url=base_url+device_interface+"?af-type=ipv4&deviceId="+device["deviceId"], verify=False).json()
                    omp = self.sess.get(url=base_url+omp_api+"?deviceId="+device["deviceId"], verify=False).json()   
                    bfd = self.sess.get(url=base_url+bfd_api+"?deviceId="+device["deviceId"], verify=False).json()  
                    tunnel = self.sess.get(url=base_url+tunnel_api+"?deviceId="+device["deviceId"], verify=False).json()
                    int_list = []
                    omp_list = []
                    bfd_list = []
                    for interface in range(len(interfaces["data"])):
                        i = interfaces["data"][interface]
                        int_list.append({"ifname":i["ifname"],
                                "vpn-id":i["vpn-id"],
                                "ip-address":i["ip-address"],
                                "tx-pkts/rx-pkts":str(i["tx-packets"] if "tx-packets" in i.keys() else "-")+"/"+str(i["rx-packets"] if "rx-packets" in i.keys() else "-"),
                                "if-status":i["if-admin-status"]+"/"+i["if-oper-status"],})
                    for peer in range(len(omp["data"])):
                        p = omp["data"][peer]
                        omp_list.append({"status":p["adminstate"]+"/"+p["operstate"]+" "+p["ompuptime"],})
                    for link in range(len(bfd["data"])):
                        b = bfd["data"][link]
                        for t in tunnel["data"]:
                            if t["dest-ip"] == b["dst-ip"]:
                                bfd_list.append({"site-id":b["site-id"],
                                    "status":b["state"]+" "+b["uptime"],
                                    "tx_pkts/rx_pkts": str(t["tx_pkts"])+"/"+str(t["rx_pkts"]),
                                    "color":b["local-color"]+"<>"+b["color"],
                                    "src-ip":b["src-ip"],
                                    "dest-ip": t["dest-ip"],})
                        for int in int_list:
                            for b in bfd_list:
                                if int["ip-address"].split("/")[0] == b["src-ip"]:
                                    b["src-ip"] = int["ifname"]
    
                    all_devices_detail.append({"site-id":device["site-id"],
                    "host-name":device["host-name"],
                    "uptime-date":str(datetime.now() - datetime.fromtimestamp(device["uptime-date"]//1000)),
                    "interfaces":tabulate(int_list,headers="keys",tablefmt="simple",disable_numparse=True),
                    "omp":tabulate(omp_list,headers="keys",tablefmt="simple"),
                    "bfd":tabulate(bfd_list,headers="keys",tablefmt="simple",disable_numparse=True),})
                else:
                    all_devices_detail.append({"site-id":device["site-id"],
                    "host-name":device["host-name"],
                    "reachability":device["reachability"],
                    })
        print(tabulate(all_devices_detail,headers="keys",tablefmt="fancy_grid"))

    def option_1(self):
        nping_results = self.nping()
        print(banner_template.render(find_host=self.find_host,vpn=self.find_vpn,vsmart=self.vsmart["stats"],omp=self.vsmart["omp"]))
        print(tabulate(nping_results,headers="keys",tablefmt="fancy_grid"))
    def option_2(self):
        self.get_find_host()
        self.get_routing()
        self.get_best_route()
        nping_results = self.nping()
        print(banner_template.render(find_host=self.find_host,vpn=self.find_vpn,vsmart=self.vsmart["stats"],omp=self.vsmart["omp"]))
        print(tabulate(nping_results,headers="keys",tablefmt="fancy_grid"))
    def option_3(self):
        self.get_routing()
        self.get_best_route()
        print("Routes updated to tool")
    #def option_4():
    #    print("option 4")
    def option_5(self):
        #print("option 5")
        self.sdwan_site_details()
    def option_6(self):
        print("Thank you. Bye!")
        exit()

if __name__ == "__main__":
    sdwan = SdWan()
    sdwan.get_find_host()
    sdwan.sdwan_login()
    sdwan.get_devices()
    sdwan.get_routing()
    sdwan.get_best_route()
    nping_results = sdwan.nping()
    print(banner_template.render(find_host=sdwan.find_host,vpn=sdwan.find_vpn,vsmart=sdwan.vsmart["stats"],omp=sdwan.vsmart["omp"]))
    print(tabulate(nping_results,headers="keys",tablefmt="fancy_grid"))
    user_input = 0
    while user_input < 7:

        print(menu_template.render(host=sdwan.find_host,vpn=sdwan.find_vpn,site=sdwan.vsmart["originator-site-id"]))

        try:
            user_input = int(input("Please select an option:",end=""))
            option_selected = getattr(sdwan,"option_"+str(user_input))
            option_selected()
        except:
            print("Does not look like a valid option. Please try again.")
            exit()
