# Troubleshootig Toolkit for Cisco SD-WAN

This python script interacts with the Cisco SD-WAN vManage REST API, to perform network troubleshooting programmatically.
Having a host IPv4 address as a starting point, this scripts attempts to:
- Locate which site ID the host was originated, using OMP prefixes the controller received;
- Managed devices (i.e.: vEdges, cEdges) generates ICMP packets using nPing to confirm reachability towards the target host;
- Gather operational, such as interface, omp, bfd details of managed devices of the site;

The idea is to have a CLI tool able to provide as much operational details as output, with minmal information as input, such as an IP or site ID.
The interaction with the tool is menu based and each option is a method or collective methods making it modular, so more functions can be added to the tool if needed. For example, interact with DDI for more information on the IP.
The output is giving in tabular for a more oginized view and has color to catch the eye. 

This script was built to interact with the [Cisco DevNet Reservable Sandbox for SD-WAN 20.4](https://devnetsandbox.cisco.com/RM/Diagram/Index/4a0f4308-1fc4-4f4c-ae8c-2734f705bd21?diagramType=Topology). So the credentials used to authenticate towards the vManage are only applicable to the Cisco Sandbox. If to use in another enviornment the varibles below would need to be changed.

## API used for this project
| Method | API path |
| --- | --- |
| `POST` | `/j_security_check` |
| `GET` | `dataservice/client/token` |
| `GET` | `/dataservice/device/interface` |
| `GET` | `/dataservice/device/omp/summary` |
| `GET` | `dataservice/device/omp/routes/received` |
| `GET` | `/dataservice/device/bfd/sessions` |
| `GET` | `/dataservice/device/tunnel/statistics` |
| `GET` | `dataservice/device/ip/routetable` |
| `POST` | `dataservice/device/tools/nping` |

For more information on available [vManage APIs v20-4](https://developer.cisco.com/docs/sdwan/#!sd-wan-vmanage-v20-4):

### Requirements
```
git clone https://github.com/apomps/CiscoSdWanToolKit
cd CiscoSdWanToolKit
pip install -r requirements.txt
```

### Example of Toolkit being used
![sdwantoolkit](https://user-images.githubusercontent.com/68168232/174201627-d6024e13-3f32-49be-aaaf-46d47da84cf4.png)

![sdwan](https://user-images.githubusercontent.com/68168232/174213051-48b85589-7312-48c0-bbab-3cdf0d477a0e.gif)


https://user-images.githubusercontent.com/68168232/174213091-5adeace7-14b4-4205-ae06-902e6217d048.mp4


# About me!
I am a Network Engineer and very excited in finding new created ways to automate... anything!

Hope this code helps you in some way!

You can find me on [LinkedIn](https://linkedin.com/in/arthur-pompeu-3459bb23)
