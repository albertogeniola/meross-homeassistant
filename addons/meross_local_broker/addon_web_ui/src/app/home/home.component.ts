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

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
})
export class HomeComponent implements AfterViewInit, OnInit {
  displayedColumns: string[] = ['deviceId', 'network', 'status', 'userId'];
  dataSource = new MatTableDataSource<Device>([]);
  autoUpdate = true;
  private _autoUpdateSubscription: Subscription = null;

  @ViewChild(MatPaginator) paginator: MatPaginator;
  @ViewChild(MatSort) sort: MatSort;

  constructor(private deviceStore: DeviceStore, public dialog: MatDialog) {}
  ngOnInit(): void {
    // Update the device list once
    this.deviceStore.devices.subscribe((devices) => (this.dataSource.data = devices));
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
    this.newDeviceName = data.device.dev_name;
  }

  onNoClick(): void {
    this.dialogRef.close();
  }

  setDeviceName(): void {
    this.deviceStore.updateDeviceName(this.data.device.uuid, this.newDeviceName).subscribe((d) => {
      if (d !== null) {
        this.data.device.dev_name = this.newDeviceName;
      }
      this.dialogRef.close();
    });
  }
}
