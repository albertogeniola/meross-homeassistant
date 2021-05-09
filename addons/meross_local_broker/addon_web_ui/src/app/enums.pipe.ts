import { Pipe, PipeTransform } from '@angular/core';
import { DeviceOnlineStatus } from './model/device';

@Pipe({ name: 'onlineDeviceStatusName' })
export class OnlineDeviceStatusName implements PipeTransform {
  transform(value: DeviceOnlineStatus): string {
    return DeviceOnlineStatus[value];
  }
}
