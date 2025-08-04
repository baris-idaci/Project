"""
nokia_parse_ont_upgrade_stats.py

Contains a filter plugin that takes the output of the 
rpc_get_onu_configuration.jinja2 RPC call and organises
the output data into list of ONTs organised by the
parent software version configured
"""
from typing import Optional
from ansible.errors import AnsibleFilterError
from pydantic import ValidationError, BaseModel, Field, field_validator


class TargetActiveSoftware(BaseModel):
    release: str


class OnuManagement(BaseModel):
    target_active_software: Optional[TargetActiveSoftware] = Field(
        None, alias='target-active-software'
    )
    target_software_control: str = Field(alias='target-software-control')


class OnuManagementState(BaseModel):
    configuration_error: Optional[str] = Field(None, alias='configuration-error')
    configuration_error_reply: Optional[str] = Field(
        None, alias='configuration-error-reply'
    )
    software_upgrading_status: str = Field(alias='software-upgrading-status')


class OnuItem(BaseModel):
    name: str
    onu_management: OnuManagement = Field(alias='onu-management')
    onu_management_state: Optional[OnuManagementState] = Field(
        None, alias='onu-management-state'
    )


class Onus(BaseModel):
    onu: list[OnuItem]

    @field_validator('onu', mode='before')
    def ensure_list(onu: list | dict) -> list[dict]:
        """
        Ensures that the ONU field is always returned as a list
        """
        if isinstance(onu, dict):
            onu = [onu]
        return onu

class DeviceSpecificData(BaseModel):
    onus: Onus


class AdhDevice(BaseModel):
    adh_device_id: str = Field(alias='adh:device-id')
    device_specific_data: DeviceSpecificData = Field(alias='device-specific-data')


class AnvDeviceManager(BaseModel):
    adh_device: AdhDevice = Field(alias='adh:device')


class Data(BaseModel):
    anv_device_manager: AnvDeviceManager = Field(alias='anv:device-manager')


class RpcReply(BaseModel):
    data: Data


class Output(BaseModel):
    rpc_reply: RpcReply = Field(alias='rpc-reply')


class NokiaGetOntStatus(BaseModel):
    output: Output

    @property
    def output_stats_model(self) -> list[dict]:
        """
        Returns a list of dictionaries containing the ONTs
        and ONT numbers organised by the parent software version
        """
        grouped_software_versions = set(
            [
                onu.onu_management.target_active_software.release
                for onu in self.output.rpc_reply.data.anv_device_manager.adh_device.device_specific_data.onus.onu
                if onu.onu_management.target_active_software
            ]
        )
        
        software_version_data = [
            {
                "software_version": software_version,
                "total_ont": len(
                    [
                        onu
                        for onu in self.output.rpc_reply.data.anv_device_manager.adh_device.device_specific_data.onus.onu
                        if onu.onu_management.target_active_software
                        and onu.onu_management.target_active_software.release == software_version
                    ]
                ),
                "configured_ont": [
                    onu.name
                    for onu in self.output.rpc_reply.data.anv_device_manager.adh_device.device_specific_data.onus.onu
                    if onu.onu_management.target_active_software
                    and onu.onu_management.target_active_software.release == software_version
                ],
            }
            for software_version in grouped_software_versions
        ]
        return software_version_data

def filter_function(input_data: dict) -> list[dict]:
    """
    Takes in the RPC output, passes it through the pydantic model
    and calls the instance method to output a list of dictionaries
    containing the statistics for the ONT upgrade process
    
    Args:
        input_data (dict): The parsed RPC response from
    
    Return:
        list[dict]: A list of dictionaries in the following format:
   
        [
            {
                "software_version": "R22.03.00a",
                "total_ont": 5,
                "configured_ont": [
                    19214414,
                    19214415,
                    19214416,
                    19214417,
                    19214418,
                ]
            }
        ]
    """
    try:
        model_rpc = NokiaGetOntStatus(**input_data)
        return model_rpc.output_stats_model

    except ValidationError as e:
        raise AnsibleFilterError(
            "Failed to parse RPC correctly, check the RPC output is "
            f"defined as expected in the datamodel: {e}"
            )


class FilterModule:
    """
    FilterModule class for makin
    """
    filter_map = {
        'parse_nokia_ont_upgrade_stats': filter_function,
    }
    def filters(self):
        """
        Returns the available filters to ansible

        Returns:
            dict: list of filters and the functions to call
            when someone uses it
        """
        return self.filter_map
