export enum DeviceOnlineStatus {
  UNKNOWN = -1,
  NOT_ONLINE = 0,
  ONLINE = 1,
  OFFLINE = 2,
  UPGRADING = 3

}

export interface Device {
  mac: string;
  uuid: string;
  deviceName: string;
  deviceType: string;
  deviceSubType: string;
  firmwareVersion: string;
  domain: string;
  reservedDomain: string;
  userId: string;
  status: DeviceOnlineStatus;
}
