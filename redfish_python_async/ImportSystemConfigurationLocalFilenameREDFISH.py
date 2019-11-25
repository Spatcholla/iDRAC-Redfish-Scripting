import asyncio
import json
import logging
import pathlib
import re
import sys
import time
from typing import IO

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
    target: str,
    shutdown: str,
    filename: str,
    end_state: str,
    output_file: IO,
) -> None:
    """Crawl & write concurrently to `file` for multiple `urls`."""
    job = locals()

    config = get_config(filename)
    job['node'] = '3VC6BZ2'

    auth = aiohttp.BasicAuth(login=username, password=password)

    async with ClientSession(auth=auth) as job["session"]:
        post_results = await post_config(config=config, **job)
        job.update(**post_results)
        if "job_id" in job:
            status_results = await parse_status(**job)
            job.update(**status_results)
        await write_status(**job)


async def write_status(output_file: IO, **kwargs) -> None:
    """Write the status of job from `node` to `file`."""
    pass
    # print(kwargs)
    # if not res:
    #     return None
    # async with aiofiles.open(file, "a") as f:
    #     for p in res:
    #         await f.write(f"{url}\t{p}\n")
    #     logger.info(f"Wrote results for source URL: {url}")


async def parse_status(ip: str, session: ClientSession, job_id: str, **kwargs) -> dict:
    """Find HREFs in the HTML of `url`."""
    job = dict()
    counter = 0
    while True:
        try:
            response = await get_status(ip=ip, job_id=job_id, session=session)
        except (aiohttp.ClientError, aiohttp.ClientConnectionError,) as e:
            logger.error(
                f"aiohttp exception for {ip} [{getattr(e, 'status', None)}]: {getattr(e, 'message', None),}"
            )
            job['error'] = e
            return job
        except Exception as e:
            logger.exception(
                f"Non-aiohttp exception occured: {getattr(e, '__dict__', {})}"
            )
            job['error'] = e
            return job

        data = response.json()
        if response.status != 202 or 200:
            counter += 1
            logger.info(f"RETRY -- Got response [{response.status}] for {ip}; attempt: {counter}")
            if counter > 10:
                return job
            await asyncio.sleep(10)
            continue

        fail_messages = [
            "failed",
            "completed with errors",
            "Not one",
            "not compliant",
            "Unable",
            "The system could not be shut down",
            "No device configuration",
        ]

        success_messages = [
            "Successfully imported",
            "completed with errors",
            "Successfully imported",
        ]

        reboot_messages = [
            "No reboot Server",
        ]

        no_change_messages = [
            "No changes",
            "No configuration changes",
        ]

        def job_state(states: list, message: str) -> list:
            return [state for state in states if state in message]

        if any(
            job_state(states=fail_messages, message=data["Oem"]["Dell"]["Message"])
        ):
            logger.info(
                f"FAIL -- {job['job_id']} marked as {data['Oem']['Dell']['JobState']} but detected issue(s). "
                f"See detailed job results below for more information on failure\n"
                f"Detailed job results for {job['job_id']}\n"
                f"{data['Oem']['Dell']}\n"
                f"{data['Messages']}\n"
            )
            job["status"] = "failed"
            return job

        elif any(
            job_state(
                states=reboot_messages, message=data["Oem"]["Dell"]["Message"]
            )
        ):
            logger.info(
                f"REBOOT -- job ID {job['job_id']} successfully marked completed. NoReboot value detected and "
                f"config changes will not be applied until next manual server reboot\n"
                f"Detailed job results for {job['job_id']}\n"
                f"{data['Oem']['Dell']}\n"
                f"{data['Messages']}\n"
            )
            job["status"] = "reboot needed"
            return job

        elif any(
            job_state(
                states=success_messages, message=data["Oem"]["Dell"]["Message"]
            )
        ):
            end = time.perf_counter_ns()
            completion_time = (end - job["start"]) / 1e9

            logger.info(
                f"SUCCESS -- job ID {job['job_id']} successfully marked completed\n"
                f"Detailed job results for job ID {job['job_id']}\n"
                f"{data['Oem']['Dell']}\n"
                f"{job['job_id']} completed in: {completion_time:.02f} seconds\n"
                f"Config results for job ID {job['job_id']}\n"
                f"{data['Messages']}\n"
            )
            job["end"] = end
            job["completion_time"] = completion_time
            job["status"] = "completed"
            return job

        elif any(
            job_state(
                states=no_change_messages, message=data["Oem"]["Dell"]["Message"]
            )
        ):
            logger.info(
                f"NO CHANGE -- job ID {job['job_id']} marked completed\n"
                f"Detailed job results for job ID {job['job_id']}\n"
            )
            job["status"] = "no change"
            return job

        else:
            logger.info(
                f"STATUS -- JobStatus not completed, current status: {data['Oem']['Dell']['Message']}, "
                f"percent complete: {data['Oem']['Dell']['PercentComplete']}"
            )
            await asyncio.sleep(10)
            continue


async def get_status(
    ip: str, session: ClientSession, job_id: str,
) -> aiohttp.ClientResponse:
    response = await session.get(
        url=f"https://{ip}/redfish/v1/TaskService/Tasks/{job_id}", ssl=False,
    )
    return response


async def post_config(
    config: str,
    end_state: str,
    ip: str,
    node: str,
    session: ClientSession,
    shutdown: str,
    target: str,
    **kwargs: dict,
) -> dict:
    """POST request wrapper to push iDRAC configuration.
    """
    url = f"https://{ip}/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ImportSystemConfiguration"

    payload = {"ImportBuffer": "", "ShareParameters": {"Target": target}}
    if shutdown:
        payload["ShutdownType"] = shutdown
    if end_state:
        payload["HostPowerState"] = end_state

    payload["ImportBuffer"] = config
    headers = {"content-type": "application/json"}

    response = await session.post(
        url=url, data=json.dumps(payload), headers=headers, ssl=False,
    )
    response.raise_for_status()
    logger.info(f"Got response [{response.status}] for {node}")

    try:
        job_id = re.search("JID_\d+", str(response)).group()
    except:
        print(f"\n- FAIL: status code {response.status} returned")
        print(f"- Detailed error information: {response}")

    if response.status != 202:
        logger.info(f"FAIL -- Got response [{response.status}] for {node}")
    else:
        print(
            f"\n- {job_id} successfully created for ImportSystemConfiguration method\n"
        )
        logger.info(f"SUCCESS -- {job_id} successfully created for {node}")

    start = time.perf_counter_ns()

    job = {
        "job_id": job_id,
        "start": start,
    }

    return job


def get_config(filename: str) -> str:
    path = pathlib.Path(filename)
    try:
        with path.open("r") as fin:
            config = fin.read()
            config = re.sub(" \n ", "", config)
            config = re.sub(" \n", "", config)
            config = re.sub("   ", "", config)
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
    # parser.add_argument(
    #     "script_examples",
    #     action="store_true",
    #     help="ImportSystemConfigurationLocalFilenameREDFISH.py -ip 192.168.0.120 -u root -p calvin -t ALL "
    #          "-f SCP_export_R740, this example is going to import SCP file and apply all attribute changes "
    #          "for all components. \nImportSystemConfigurationLocalFilenameREDFISH.py -ip 192.168.0.120 "
    #          "-u root -p calvin -t BIOS --filename R740_scp_file -s Forced, this example is going to only "
    #          "apply BIOS changes from the SCP file along with forcing a server power reboot.",
    # )
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

    asyncio.run(main(output_file=outfile, **args))
