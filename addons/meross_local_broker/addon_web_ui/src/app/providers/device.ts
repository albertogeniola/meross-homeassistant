import { Injectable } from '@angular/core';
import { Device } from '@app/model/device';
import { BehaviorSubject, defer, interval, Observable } from 'rxjs';
import { AdminService } from '../services/admin';
import { timer, from } from 'rxjs'
import { map, concatMap, repeatWhen, share, tap, publishReplay, shareReplay, switchMap, takeUntil } from 'rxjs/operators'


@Injectable({
    providedIn: 'root'
})
export class DeviceStore {
    // Internal device handler
    private _devices: BehaviorSubject<Device[]> = new BehaviorSubject([]);

    // Exposed observable
    public readonly devices: Observable<Device[]> = this._devices.asObservable();
    public readonly deviceUpdates: Observable<Device[]> = interval(2000).pipe(
        switchMap(() => this.devicesUpdate()),
        //takeUntil(this.reload$),
        share()
      );

    constructor(private adminService: AdminService) {
        // Perform a first poll
        this.devicesUpdate().pipe(tap(e=>console.log(e))).subscribe(
            devices => this._devices.next(devices)
        );
    }

    private devicesUpdate(): Observable<Device[]> {
        return this.adminService.listDevices();
    }
}