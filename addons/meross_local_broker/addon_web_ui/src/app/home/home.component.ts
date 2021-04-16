import { Component, AfterViewInit, ViewChild, OnInit, Inject } from '@angular/core';
import { MatTableDataSource } from '@angular/material/table';
import { MatSort } from '@angular/material/sort';
import { MatPaginator } from '@angular/material/paginator';
import { finalize } from 'rxjs/operators';
import { Device, DeviceOnlineStatus } from '@app/model/device';
import { DeviceStore } from '@app/providers/device';
import { AdminService } from '@app/services/admin';
import { MatSlideToggleChange } from '@angular/material/slide-toggle';
import { Observable, Subscription } from 'rxjs';
import { MatDialog, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';

export interface SetNameDialogData {
  device: Device;
}

var mock: Device[] = [
  {
    device_name: null,
    device_sub_type: null,
    device_type: null,
    domain: null,
    firmware_version: null,
    hardware_version: null,
    last_seen_time: new Date('Fri, 16 Apr 2021 09:17:23 GMT'),
    mac: '34:29:8f:1a:5b:2d',
    online_status: DeviceOnlineStatus.OFFLINE,
    reserved_domain: null,
    user_id: '1',
    uuid: '19011890809879251h0434298f1a5b2d',
  },
];

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
})
export class HomeComponent implements AfterViewInit, OnInit {
  displayedColumns: string[] = ['deviceId', 'network', 'status'];
  dataSource = new MatTableDataSource<Device>([]);
  autoUpdate = true;
  private _autoUpdateSubscription: Subscription = null;

  @ViewChild(MatPaginator) paginator: MatPaginator;
  @ViewChild(MatSort) sort: MatSort;

  constructor(private deviceStore: DeviceStore, public dialog: MatDialog) {}
  ngOnInit(): void {
    // Update the device list once
    this.dataSource.data = mock;
    //this.deviceStore.devices.subscribe((devices) => (this.dataSource.data = devices));
  }

  onAutodeviceUpdate(e: MatSlideToggleChange) {
    if (e.checked === true) {
      if (this._autoUpdateSubscription !== null) this._autoUpdateSubscription.unsubscribe();
      this._autoUpdateSubscription = this.deviceStore.deviceUpdates.subscribe(
        (devices) => (this.dataSource.data = devices)
      );
    } else {
      if (this._autoUpdateSubscription !== null) this._autoUpdateSubscription.unsubscribe();
    }
  }

  ngAfterViewInit() {
    this.dataSource.paginator = this.paginator;
    this.dataSource.sort = this.sort;
  }

  assignName(device: Device) {
    const dialogRef = this.dialog.open(SetDeviceNameDialog, {
      data: { device: device },
    });

    dialogRef.afterClosed().subscribe((result) => {
      console.log('The dialog was closed');
      //this.animal = result;
    });
  }
}

@Component({
  selector: 'set-device-name-dialog',
  templateUrl: 'set-device-name-dialog.html',
})
export class SetDeviceNameDialog {
  newDeviceName: string;

  constructor(
    public dialogRef: MatDialogRef<SetDeviceNameDialog>,
    private deviceStore: DeviceStore,
    @Inject(MAT_DIALOG_DATA) public data: SetNameDialogData
  ) {
    this.newDeviceName = data.device.device_name;
  }

  onNoClick(): void {
    this.dialogRef.close();
  }

  setDeviceName(): void {
    this.deviceStore.updateDeviceName(this.data.device.uuid, this.newDeviceName).subscribe((d) => {
      this.data.device = d;
      this.dialogRef.close();
    });
  }
}
