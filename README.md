== check_sas_smart
Check SMART values of SAS disks.

This check is supposed to be used with with Icinga2 by defining a command
object like so:
```
object CheckCommand "sasSOS" {
  import "plugin-check-command"
  command = [PluginDir + "/check_sas_smart" ]

  arguments = {
    "-d" = {
      value = "$my_device$"
      description = "Device to check"
      required = true
      skip_key = true
    }
  }
  
  vars.my_device = "$device$"
}
```
and then templating it like so:
```
apply Service "sas " for (sas => config in host.vars.sas) {
  import "long-service"
  check_command = "sasSOS"

  vars += config
}
```
and finally setting something like this in the host variables:
```
  vars.sas["/dev/sda"] = {
    device = "/dev/sda"
  }
```

=== Example output
```
OK disk /dev/sda | 'Temperature'=39c;42;46 'Non_media_errors'=0c 'Power_On_Hours'=11860c 'InvalidDWORD'=0c 'DWORDSyncLoss'=2c 'PhyResetProblems'=0c 'ReadCorrectedECCFast'=70655970102c 'ReadCorrectedECCSlow'=0c 'ReadCorrectedRedo'=70655970102c 'ReadCorrectedTotal'=70655970102c 'ReadUncorrectedTotal'=0c;1;3 'WriteCorrectedECCFast'=0c 'WriteCorrectedECCSlow'=0c 'WriteCorrectedRedo'=0c 'WriteCorrectedTotal'=0c 'WriteUncorrectedTotal'=0c;1;3
OK: Temperature = 39
OK: Non_media_errors = 0
OK: Power_On_Hours = 11860
OK: InvalidDWORD = 0
OK: DWORDSyncLoss = 2
OK: PhyResetProblems = 0
OK: ReadCorrectedECCFast = 70655970102
OK: ReadCorrectedECCSlow = 0
OK: ReadCorrectedRedo = 70655970102
OK: ReadCorrectedTotal = 70655970102
OK: ReadUncorrectedTotal = 0
OK: WriteCorrectedECCFast = 0
OK: WriteCorrectedECCSlow = 0
OK: WriteCorrectedRedo = 0
OK: WriteCorrectedTotal = 0
OK: WriteUncorrectedTotal = 0
```
