import { Pipe, PipeTransform } from '@angular/core';
import { BridgeStatus, DeviceOnlineStatus } from './model/device';

@Pipe({ name: 'onlineDeviceStatusName' })
export class OnlineDeviceStatusName implements PipeTransform {
  transform(value: DeviceOnlineStatus): string {
    return DeviceOnlineStatus[value];
  }
}

@Pipe({ name: 'bridgeStatusName' })
export class BridgeStatusName implements PipeTransform {
  transform(value: BridgeStatus): string {
    return BridgeStatus[value];
  }
}
