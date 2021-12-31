"""Contains functions for parsing files in IOS Shell format."""
import datetime
import fortranformat as ff
import re
from typing import Any, Dict, List, Tuple

from . import sections, utils
from .utils import DATE_STR, TIME_STR
from .keys import *


def _next_line(rest: str) -> List[str]:
    return rest.split("\n", 1)  # pragma: no mutate


def get_modified_date(contents: str) -> Tuple[datetime.datetime, str]:
    rest = contents.lstrip()
    if m := re.match(fr"\*({DATE_STR} {TIME_STR})", rest):
        rest = rest[m.end() :]
        return (utils.to_datetime(m.group(1)), rest)
    else:
        raise ValueError("No modified date at start of string")


def get_header_version(contents: str) -> Tuple[sections.Version, str]:
    rest = contents.lstrip()
    match_version = r"(?P<version_no>\d+.\d+)"
    match_date1 = f"(?P<date1>{DATE_STR})"
    match_date2 = f"(?P<date2>{DATE_STR})"
    match_tag = "(?P<tag>[a-zA-Z0-9.]+)"
    if m := re.match(
        fr"\*IOS HEADER VERSION +{match_version} +{match_date1}( +{match_date2}( +{match_tag})?)?",
        rest,
    ):
        rest = rest[m.end() :]
        return (sections.Version(**m.groupdict()), rest)
    else:
        raise ValueError("No header version in string")


def get_section(contents: str, section_name: str) -> Tuple[Dict[str, Any], str]:
    rest = contents.lstrip()
    prefix = f"*{section_name.upper()}\n"
    section_info: Dict[str, Any] = {}
    if not rest.startswith(prefix):
        raise ValueError(
            f"{section_name.upper()} section not present, found {_next_line(rest)[0]} instead"
        )
    rest = rest[len(prefix) :]
    while not utils.is_section_heading(rest.lstrip()):
        rest = rest.lstrip()
        if rest.startswith("!"):
            # skip comments
            _, rest = _next_line(rest)
            continue
        elif m := re.match(r"\$TABLE: ([^\n]+)\n", rest):
            # handle table
            table_name = m.group(1).lower()
            rest = rest[m.end() :]
            # table column names
            line, rest = _next_line(rest)
            column_names_line = line
            # table column mask
            line, rest = _next_line(rest)
            mask = [c == "-" for c in line]
            # apply column mask in case names contain spaces
            column_names = [
                name.lower().strip().replace(" ", "_")
                for name in utils.apply_column_mask(column_names_line, mask)
            ]
            # values
            section_info[table_name] = []
            while not rest.lstrip().startswith("$END"):
                line, rest = _next_line(rest)
                section_info[table_name].append(
                    {
                        column_names[i]: v
                        for i, v in enumerate(utils.apply_column_mask(line, mask))
                    }
                )
            _, rest = _next_line(rest.lstrip())
        elif m := re.match(r"\$ARRAY: ([^\n]+)\n", rest):
            array_name = m.group(1).lower()
            rest = rest[m.end() :]
            section_info[array_name] = []
            while not rest.lstrip().startswith("$END"):
                line, rest = _next_line(rest)
                section_info[array_name].append(line)
            _, rest = _next_line(rest.lstrip())
        elif m := re.match(r"\$REMARKS?", rest):
            # handle remarks
            rest = rest[m.end() :]
            remarks = []
            while not rest.lstrip().startswith("$END"):
                line, rest = _next_line(rest)
                remarks.append(line)
            section_info[REMARKS] = "\n".join(remarks)  # pragma: no mutate
            _, rest = _next_line(rest.lstrip())
        else:
            # handle single entry
            line, rest = _next_line(rest)
            key, value = line.split(":", 1)
            section_info[key.strip().lower()] = value.strip()
    return section_info, rest


def get_file(contents: str) -> Tuple[sections.FileInfo, str]:
    file_dict, rest = get_section(contents, "file")
    start_time = (
        utils.to_datetime(file_dict[START_TIME])
        if START_TIME in file_dict
        else datetime.datetime.min
    )
    end_time = (
        utils.to_datetime(file_dict[END_TIME])
        if END_TIME in file_dict
        else datetime.datetime.min
    )
    time_zero = (
        utils.to_datetime(file_dict[TIME_ZERO])
        if TIME_ZERO in file_dict
        else datetime.datetime.min
    )
    number_of_records = int(file_dict[NUMBER_OF_RECORDS])
    data_description = (
        file_dict[DATA_DESCRIPTION] if DATA_DESCRIPTION in file_dict else ""
    )
    file_type = file_dict[FILE_TYPE] if FILE_TYPE in file_dict else ""
    number_of_channels = int(file_dict[NUMBER_OF_CHANNELS])
    channels = (
        [sections.Channel(**elem) for elem in file_dict[CHANNELS]]
        if CHANNELS in file_dict
        else []
    )
    channel_details = (
        [sections.ChannelDetail(**elem) for elem in file_dict[CHANNEL_DETAIL]]
        if CHANNEL_DETAIL in file_dict
        else []
    )
    remarks = file_dict[REMARKS] if REMARKS in file_dict else ""
    data_type = file_dict[DATA_TYPE] if DATA_TYPE in file_dict else ""
    to_remove = " \n\t'"  # pragma: no mutate
    if FORMAT in file_dict:
        format_str = file_dict[FORMAT].strip(to_remove)
        if CONTINUED in file_dict:
            format_str += file_dict[CONTINUED].strip(to_remove)
    else:
        format_info = [
            utils.format_string(detail.format, detail.width, detail.decimal_places)
            for detail in channel_details
        ]
        format_str = "({})".format(",".join(format_info))
    file_info = sections.FileInfo(
        start_time=start_time,
        end_time=end_time,
        time_zero=time_zero,
        number_of_records=number_of_records,
        data_description=data_description,
        file_type=file_type,
        format=format_str,
        data_type=data_type,
        number_of_channels=number_of_channels,
        channels=channels,
        channel_details=channel_details,
        remarks=remarks,
        raw=file_dict,
    )
    return file_info, rest


def get_administration(contents: str) -> Tuple[sections.Administration, str]:
    admin_dict, rest = get_section(contents, "administration")
    mission = admin_dict[MISSION] if MISSION in admin_dict else ""
    agency = admin_dict[AGENCY] if AGENCY in admin_dict else ""
    country = admin_dict[COUNTRY] if COUNTRY in admin_dict else ""
    project = admin_dict[PROJECT] if PROJECT in admin_dict else ""
    scientist = admin_dict[SCIENTIST] if SCIENTIST in admin_dict else ""
    platform = admin_dict[PLATFORM] if PLATFORM in admin_dict else ""
    remarks = admin_dict[REMARKS] if REMARKS in admin_dict else ""
    admin_info = sections.Administration(
        mission=mission,
        agency=agency,
        country=country,
        project=project,
        scientist=scientist,
        platform=platform,
        remarks=remarks,
        raw=admin_dict,
    )
    return admin_info, rest


def get_location(contents: str) -> Tuple[sections.Location, str]:
    location_dict, rest = get_section(contents, "location")
    geographic_area = (
        location_dict[GEOGRAPHIC_AREA] if GEOGRAPHIC_AREA in location_dict else ""
    )
    station = location_dict[STATION] if STATION in location_dict else ""
    event_number = (
        int(location_dict[EVENT_NUMBER]) if EVENT_NUMBER in location_dict else -1
    )
    latitude = utils.get_latitude(location_dict[LATITUDE])
    longitude = utils.get_longitude(location_dict[LONGITUDE])
    water_depth = (
        float(location_dict[WATER_DEPTH])
        if WATER_DEPTH in location_dict
        and location_dict[WATER_DEPTH].lower() not in ["", "unknown"]
        else -1
    )
    remarks = location_dict[REMARKS] if REMARKS in location_dict else ""
    location_info = sections.Location(
        geographic_area=geographic_area,
        station=station,
        event_number=event_number,
        latitude=latitude,
        longitude=longitude,
        water_depth=water_depth,
        remarks=remarks,
        raw=location_dict,
    )
    return location_info, rest


def get_instrument(contents: str) -> Tuple[sections.Instrument, str]:
    instrument_dict, rest = get_section(contents, "instrument")
    kind = instrument_dict[TYPE] if TYPE in instrument_dict else ""
    model = instrument_dict[MODEL] if MODEL in instrument_dict else ""
    remarks = instrument_dict[REMARKS] if REMARKS in instrument_dict else ""
    instrument_info = sections.Instrument(
        type=kind,
        model=model,
        remarks=remarks,
        raw=instrument_dict,
    )
    return instrument_info, rest


def get_history(contents: str) -> Tuple[sections.History, str]:
    history_dict, rest = get_section(contents, "history")
    programs = (
        [sections.Program(*elem) for elem in history_dict[PROGRAMS]]
        if PROGRAMS in history_dict
        else []
    )
    remarks = history_dict[REMARKS] if REMARKS in history_dict else ""
    history_info = sections.History(
        programs=programs,
        remarks=remarks,
        raw=history_dict,
    )
    return history_info, rest


def get_calibration(contents: str) -> Tuple[sections.Calibration, str]:
    calibration_dict, rest = get_section(contents, "calibration")
    corrected_channels = (
        calibration_dict[CORRECTED_CHANNELS]
        if CORRECTED_CHANNELS in calibration_dict
        else []
    )
    remarks = calibration_dict[REMARKS] if REMARKS in calibration_dict else ""
    calibration_info = sections.Calibration(
        corrected_channels=corrected_channels,
        remarks=remarks,
        raw=calibration_dict,
    )
    return calibration_info, rest


def get_raw(contents: str) -> Tuple[sections.Raw, str]:
    raw_dict, rest = get_section(contents, "raw")
    remarks = raw_dict[REMARKS] if REMARKS in raw_dict else ""
    raw_info = sections.Raw(
        remarks=remarks,
        raw=raw_dict,
    )
    return raw_info, rest


def get_deployment(contents: str) -> Tuple[sections.Deployment, str]:
    deployment_dict, rest = get_section(contents, "deployment")
    mission = deployment_dict[MISSION] if MISSION in deployment_dict else ""
    type = deployment_dict[TYPE] if TYPE in deployment_dict else ""
    anchor_dropped = (
        utils.to_datetime(deployment_dict[TIME_ANCHOR_DROPPED])
        if TIME_ANCHOR_DROPPED in deployment_dict
        else datetime.datetime.min
    )
    remarks = deployment_dict[REMARKS] if REMARKS in deployment_dict else ""
    deployment_info = sections.Deployment(
        mission=mission,
        type=type,
        anchor_dropped=anchor_dropped,
        remarks=remarks,
        raw=deployment_dict,
    )
    return deployment_info, rest


def get_recovery(contents: str) -> Tuple[sections.Recovery, str]:
    recovery_dict, rest = get_section(contents, "recovery")
    mission = recovery_dict[MISSION] if MISSION in recovery_dict else ""
    anchor_released = (
        utils.to_datetime(recovery_dict[TIME_ANCHOR_RELEASED])
        if TIME_ANCHOR_RELEASED in recovery_dict
        else datetime.datetime.min
    )
    remarks = recovery_dict[REMARKS] if REMARKS in recovery_dict else ""
    recovery_info = sections.Recovery(
        mission=mission,
        anchor_released=anchor_released,
        remarks=remarks,
        raw=recovery_dict,
    )
    return recovery_info, rest


def get_comments(contents: str) -> Tuple[str, str]:
    rest = contents.lstrip()
    if m := re.match(r"\*COMMENTS\n", rest):
        rest = rest[m.end() :]
        lines = []
        while not utils.is_section_heading(rest):
            line, rest = _next_line(rest)
            lines.append(line)
        return "\n".join(lines), rest
    else:
        raise ValueError("No COMMENTS section found")


def _has_date(contents: str) -> bool:
    return re.search(DATE_STR, contents) is not None


def _has_time(contents: str) -> bool:
    return re.search(TIME_STR, contents) is not None


def _process_item(contents: Any) -> Any:
    if not isinstance(contents, str):
        return contents
    has_date = _has_date(contents)
    has_time = _has_time(contents)
    if has_date and has_time:
        return utils.to_datetime(contents)
    elif has_date:
        return utils.to_date(contents)
    elif has_time:
        return utils.to_time(contents)
    else:
        return contents.strip()


def _postprocess_line(line: List[Any]) -> List[Any]:
    return [_process_item(item) for item in line]


def get_data(contents: str, format: str, records: int) -> Tuple[List[List[Any]], str]:
    rest = contents.lstrip()
    if m := re.match(r"\*END OF HEADER\n", rest):
        rest = rest[m.end() :]
        lines = rest.split("\n")
        while "" in lines:
            lines.remove("")
        reader = ff.FortranRecordReader(format)
        data = [_postprocess_line(reader.read(line)) for line in lines[:records]]
        rest = "\n".join(lines[records:])  # pragma: no mutate
        return data, rest
    else:
        raise ValueError("No data in file")
