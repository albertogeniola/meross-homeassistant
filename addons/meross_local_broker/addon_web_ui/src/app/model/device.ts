export enum DeviceOnlineStatus {
  UNKNOWN = -1,
  NOT_ONLINE = 0,
  ONLINE = 1,
  OFFLINE = 2,
  UPGRADING = 3,
}

export interface Device {
  readonly mac: string;
  readonly uuid: string;
  readonly device_type: string;
  readonly sub_type: string;
  readonly fmware_version: string;
  readonly hdware_version: string;
  readonly user_id: string;
  readonly online_status: DeviceOnlineStatus;
  readonly last_seen_time: Date;
  dev_name: string;
  domain: string;
  reserved_domain: string;
}
