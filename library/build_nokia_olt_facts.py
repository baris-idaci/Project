"""
build_nokia_olt_facts.py

Pass in the device name and the rpc-reply data from AVP and we will build a
facts module that will create a card inventory for the device, along with
the last state.
"""
from typing import List, Optional, Union
from ansible.module_utils.basic import AnsibleModule
from ansible.errors import AnsibleError
from pydantic import ValidationError, BaseModel, Field, model_serializer


class Duid(BaseModel): # pylint: disable=missing-class-docstring
    duids: Union[str, List[str]]


class State(BaseModel): # pylint: disable=missing-class-docstring
    admin_state: str = Field(..., alias="admin-state")
    oper_state: str = Field(..., alias="oper-state")
    standby_state: str = Field(..., alias="standby-state")


class ComponentItem(BaseModel): # pylint: disable=missing-class-docstring
    class_: str = Field(..., alias="class")
    contains_child: Optional[List[str]] = Field(None, alias="contains-child")
    description: str
    duid: Duid
    hardware_rev: str = Field(..., alias="hardware-rev")
    is_fru: str = Field(..., alias="is-fru")
    last_self_test_error: str = Field(..., alias="last-self-test-error")
    local_network_address: str = Field(..., alias="local-network-address")
    mfg_name: str = Field(..., alias="mfg-name")
    model_name: str = Field(..., alias="model-name")
    name: str
    parent: str
    parent_rel_pos: str = Field(..., alias="parent-rel-pos")
    serial_num: str = Field(..., alias="serial-num")
    state: State


class HardwareState(BaseModel): # pylint: disable=missing-class-docstring
    component: List[ComponentItem]


class DeviceSpecificData(BaseModel): # pylint: disable=missing-class-docstring
    hardware_state: HardwareState = Field(..., alias="hardware-state")


class AdhDevice(BaseModel): # pylint: disable=missing-class-docstring
    adh_device_id: str = Field(..., alias="adh:device-id")
    device_specific_data: DeviceSpecificData = Field(..., alias="device-specific-data")


class AnvDeviceManager(BaseModel): # pylint: disable=missing-class-docstring
    adh_device: AdhDevice = Field(..., alias="adh:device")


class Data(BaseModel): # pylint: disable=missing-class-docstring
    anv_device_manager: AnvDeviceManager = Field(..., alias="anv:device-manager")


class RpcReply(BaseModel): # pylint: disable=missing-class-docstring
    data: Data


class Output(BaseModel): # pylint: disable=missing-class-docstring
    rpc_reply: RpcReply = Field(..., alias="rpc-reply")


class RpcGetLinecards(BaseModel):
    """
    Root Pydantic model for RPC input validation
    """
    output: Output
    hostname: str | None = None

    @model_serializer
    def serialise_output(self):
        """
        Pydantic serialiser for the output model,

        """
        return {
            "hostname": self.hostname,
            "lt": [
                {
                    "card": f"{item.name.split('-')[-1]}.{self.hostname}",
                    "state": item.state,
                }
                for item in (
                    self.output.rpc_reply.data.anv_device_manager.adh_device
                    .device_specific_data.hardware_state.component
                )
                if item.model_name == "LWLT-C"
            ],
            "nt": [
                {
                    "card": item.name,
                    "state": item.state,
                }
                for item in (
                    self.output.rpc_reply.data.anv_device_manager.adh_device
                    .device_specific_data.hardware_state.component
                )
                if item.model_name == "LMNT-B"
            ],
        }


def main():
    """ 
    Main entry point for the module.

    Module args:
      device: The device name (appended to the linecard name)
      rpc_reply: The rpc-reply data from the AVP in rpc_get_linecards.xml.jinja2
    """
    module = AnsibleModule(
        argument_spec={
            "device": {"type": "str", "required": True},
            "rpc_reply": {"type": "dict", "required": True},
            }
        )

    device = module.params["device"]
    rpc_reply = module.params["rpc_reply"]

    try:
        datamodel = RpcGetLinecards(**rpc_reply)
        datamodel.hostname = device
        output = datamodel.model_dump()
    except ValidationError as e:
        raise AnsibleError(
            f"nokia_olt_facts.py:[create_olt_component_list] - [ERROR]: '{e}'"
        ) from e

    module.exit_json(changed=False, ansible_facts={"olt_card_inventory": output})


if __name__ == "__main__":
    main()
