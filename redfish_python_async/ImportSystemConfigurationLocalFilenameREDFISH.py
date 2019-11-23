#
# ImportSystemConfigurationLocalFilenameREDFISH. Python script using Redfish API to import system configuration profile attributes locally from a configuration file.
#
# _author_ = Texas Roemer <Texas_Roemer@Dell.com>
# _version_ = 8.0
#
# Copyright (c) 2017, Dell, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#

from datetime import datetime

import asyncio
import json
import logging
import pathlib
import re
import sys
import time
from typing import IO

import urllib.error
import urllib.parse

import aiofiles
import aiohttp
from aiohttp import ClientSession

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    level=logging.DEBUG,
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("areq")
logging.getLogger("chardet.charsetprober").disabled = True


async def main(
    ip: str,
    username: str,
    password: str,
    script_examples: str,
    target: str,
    shutdown: str,
    filename: str,
    end_state: str,
    file: IO
) -> None:
    """Crawl & write concurrently to `file` for multiple `urls`."""
    config = get_config(filename)

    url = f"https://{ip}/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ImportSystemConfiguration"

    payload = {"ImportBuffer": "", "ShareParameters": {"Target": target}}
    if shutdown:
        payload["ShutdownType"] = shutdown
    if end_state:
        payload["HostPowerState"] = end_state

    payload["ImportBuffer"] = config
    headers = {"content-type": "application/json"}
    auth = aiohttp.BasicAuth(login=username, password=password)

    async with ClientSession(auth=auth) as session:
        tasks = []
        tasks.append(
            write_status(file=file, url=url, session=session, headers=headers, payload=payload)
        )
        await asyncio.gather(*tasks)


# async def parse(url: str, session: ClientSession, **kwargs) -> set:
#     """Find HREFs in the HTML of `url`."""
#     found = set()
#     try:
#         html = await fetch_html(url=url, session=session, **kwargs)
#     except (
#         aiohttp.ClientError,
#         aiohttp.http_exceptions.HttpProcessingError,
#     ) as e:
#         logger.error(
#             f"aiohttp exception for {url} [{getattr(e, 'status', None)}]: {getattr(e, 'message', None),}"
#         )
#         return found
#     except Exception as e:
#         logger.exception(
#             "Non-aiohttp exception occured:  %s", getattr(e, "__dict__", {})
#         )
#         return found
#     else:
#         for link in HREF_RE.findall(html):
#             try:
#                 abslink = urllib.parse.urljoin(url, link)
#             except (urllib.error.URLError, ValueError):
#                 logger.exception("Error parsing URL: %s", link)
#                 pass
#             else:
#                 found.add(abslink)
#         logger.info("Found %d links for %s", len(found), url)
#         return found

async def write_status(file: IO, url: str, **kwargs) -> None:
    """Write the found response from `url` to `file`."""
    res = await post_config(url=url, **kwargs)
    if not res:
        return None
    async with aiofiles.open(file, "a") as f:
        for p in res:
            await f.write(f"{url}\t{p}\n")
        logger.info(f"Wrote results for source URL: {url}")


async def post_config(
    url: str,
    session: ClientSession,
    payload: str,
    headers: dict,
) -> str:
    """POST request wrapper to push iDRAC configuration.
    """

    response = await session.post(
        url=url,
        data=json.dumps(payload),
        headers=headers,
        ssl=False,
    )
    response.raise_for_status()
    logger.info(f"Got response [{response.status}] for URL: {url}")

    print(response)
    print("\n\n\n")
    print(response.text())
    print("\n\n\n")

    d = str(response.__dict__)

    print(d)

    return d

    # try:
    #     z = re.search("JID_.+?,", d).group()
    # except:
    #     print(f"\n- FAIL: status code {response.status} returned")
    #     print(f"- Detailed error information: {d}")
    #     sys.exit()
    #
    # job_id = re.sub("[,']", "", z)
    # if response.status != 202:
    #     print(f"\n- FAIL, status code not 202\n, code is: {response.status}")
    #     sys.exit()
    # else:
    #     print(
    #         f"\n- {job_id} successfully created for ImportSystemConfiguration method\n"
    #     )
    #
    # response_output = response.__dict__
    # job_id = response_output["headers"]["Location"]
    # job_id = re.search("JID_.+", job_id).group()
    #
    # start_time = datetime.now()
    #
    # return await resp.text()
    #
    # return job_id, start_time


# async def get_job_status(
#     ip: str, username: str, password: str, job_id, start_time,
# ) -> None:
#     while True:
#         req = requests.get(
#             f"https://{ip}/redfish/v1/TaskService/Tasks/{job_id}",
#             auth=(username, password),
#             verify=False,
#         )
#         status = req.status
#         data = req.json()
#         current_time = datetime.now() - start_time
#         if status == 202 or status == 200:
#             pass
#             time.sleep(3)
#         else:
#             print(f"Query job ID command failed, error code is: {status}")
#             sys.exit()
#         if (
#             "failed" in data["Oem"]["Dell"]["Message"]
#             or "completed with errors" in data["Oem"]["Dell"]["Message"]
#             or "Not one" in data["Oem"]["Dell"]["Message"]
#             or "not compliant" in data["Oem"]["Dell"]["Message"]
#             or "Unable" in data["Oem"]["Dell"]["Message"]
#             or "The system could not be shut down" in data["Oem"]["Dell"]["Message"]
#             or "No device configuration" in data["Oem"]["Dell"]["Message"]
#         ):
#             print(
#                 f"- FAIL, Job ID {job_id} marked as {data[u'Oem'][u'Dell'][u'JobState']} but detected issue(s). "
#                 f"See detailed job results below for more information on failure\n"
#             )
#             print(f"- Detailed job results for job ID {job_id}\n")
#             for i in data["Oem"]["Dell"].items():
#                 print(f"{i[0]}: {i[1]}")
#             print(f"\n- Config results for job ID {job_id}\n")
#             for i in data["Messages"]:
#                 for ii in i.items():
#                     if ii[0] == "Oem":
#                         print("-" * 80)
#                         for iii in ii[1]["Dell"].items():
#                             print(f"{iii[0]}: {iii[1]}")
#                     else:
#                         pass
#             sys.exit()
#         elif "No reboot Server" in data["Oem"]["Dell"]["Message"]:
#             print(
#                 f"- PASS, job ID {job_id} successfully marked completed. NoReboot value detected and config changes will "
#                 f"not be applied until next manual server reboot\n"
#             )
#             print(f"\n- Detailed job results for job ID {job_id}\n")
#             for i in data["Oem"]["Dell"].items():
#                 print(f"{i[0]}: {i[1]}")
#             sys.exit()
#         elif (
#             "Successfully imported" in data["Oem"]["Dell"]["Message"]
#             or "completed with errors" in data["Oem"]["Dell"]["Message"]
#             or "Successfully imported" in data["Oem"]["Dell"]["Message"]
#         ):
#             print(f"- PASS, job ID {job_id} successfully marked completed\n")
#             print(f"- Detailed job results for job ID {job_id}\n")
#             for i in data["Oem"]["Dell"].items():
#                 print(f"{i[0]}: {i[1]}")
#             print(f"\n- {job_id} completed in: {str(current_time)[0:7]}")
#             print(f"\n- Config results for job ID {job_id}\n")
#             for i in data["Messages"]:
#                 for ii in i.items():
#                     if ii[0] == "Oem":
#                         print("-" * 80)
#                         for iii in ii[1]["Dell"].items():
#                             print(f"{iii[0]}: {iii[1]}")
#                     else:
#                         pass
#
#             sys.exit()
#         elif (
#             "No changes" in data["Oem"]["Dell"]["Message"]
#             or "No configuration changes" in data["Oem"]["Dell"]["Message"]
#         ):
#             print(f"\n- PASS, job ID {job_id} marked completed\n")
#             print(f"- Detailed job results for job ID {job_id}\n")
#             for i in data["Oem"]["Dell"].items():
#                 print(f"{i[0]}: {i[1]}")
#             sys.exit()
#         else:
#             print(
#                 f"- WARNING, JobStatus not completed, current status: {data['Oem']['Dell']['Message']}, "
#                 f"percent complete: {data['Oem']['Dell']['PercentComplete']}"
#             )
#             await asyncio.sleep(1)
#             continue


def get_config(filename: str) -> str:
    path = pathlib.Path(filename)
    try:
        with path.open("r") as fin:
            config = fin.read()
            config = re.sub(r"[\n ]", "", config)
            return config
    except FileNotFoundError as err:
        print(f"An error has occurred; please check file path.\n{err}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Python script using Redfish API to import the host server configuration profile locally from a "
        "configuration file."
    )
    parser.add_argument("-ip", help="iDRAC IP address", required=True)
    parser.add_argument("-u", "--username", help="iDRAC username", required=True)
    parser.add_argument("-p", "--password", help="iDRAC password", required=True)
    parser.add_argument(
        "script_examples",
        action="store_true",
        help="ImportSystemConfigurationLocalFilenameREDFISH.py -ip 192.168.0.120 -u root -p calvin -t ALL "
        "-f SCP_export_R740, this example is going to import SCP file and apply all attribute changes "
        "for all components. \nImportSystemConfigurationLocalFilenameREDFISH.py -ip 192.168.0.120 "
        "-u root -p calvin -t BIOS --filename R740_scp_file -s Forced, this example is going to only "
        "apply BIOS changes from the SCP file along with forcing a server power reboot.",
    )
    parser.add_argument(
        "-t",
        "--target",
        help="Pass in Target value to set component attributes. You can pass in 'ALL' to set all component attributes "
        "or pass in a specific component to set only those attributes. Supported values are: ALL, System, BIOS, "
        "IDRAC, NIC, FC, LifecycleController, RAID.",
        required=True,
    )
    parser.add_argument(
        "-s",
        "--shutdown",
        help="Pass in ShutdownType value. Supported values are Graceful, Forced and NoReboot. If you don't use this "
        "optional parameter, default value is Graceful. NOTE: If you pass in NoReboot value, configuration changes "
        "will not be applied until the next server manual reboot.",
        required=False,
    )
    parser.add_argument(
        "-f",
        "--filename",
        help="Pass in Server Configuration Profile filename",
        required=True,
    )
    parser.add_argument(
        "-e",
        "--end-state",
        help="Pass in end HostPowerState value. Supported values are On and Off. If you don't use this optional "
        "parameter, default value is On",
        required=False,
    )
    args = vars(parser.parse_args())

    here = pathlib.Path(__file__).parent

    outpath = here.joinpath("status.txt")
    with open(outpath, "w") as outfile:
        outfile.write("source_url\tstatus\n")

    asyncio.run(main(file=outfile, **args))
