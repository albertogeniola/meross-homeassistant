import { Injectable } from '@angular/core';
import { Subdevice } from '@app/model/subdevice';
import { BehaviorSubject, defer, interval, Observable } from 'rxjs';
import { AdminService } from '../services/admin';
import { timer, from } from 'rxjs';
import {
  map,
  concatMap,
  repeatWhen,
  share,
  tap,
  publishReplay,
  shareReplay,
  switchMap,
  takeUntil,
} from 'rxjs/operators';

@Injectable({
  providedIn: 'root',
})
export class SubdeviceStore {
  // Internal device handler
  private _devices: BehaviorSubject<Subdevice[]> = new BehaviorSubject([]);
  private REFRESH_TIME: number = 10000;

  // Exposed observable
  public readonly devices: Observable<Subdevice[]> = this._devices.asObservable();
  public readonly deviceUpdates: Observable<Subdevice[]> = interval(this.REFRESH_TIME).pipe(
    switchMap(() => this.devicesUpdate()),
    //takeUntil(this.reload$),
    share()
  );

  constructor(private adminService: AdminService) {
    // Perform a first poll
    this.devicesUpdate()
      .pipe(tap((e) => console.log(e)))
      .subscribe((devices) => this._devices.next(devices));
  }

  private devicesUpdate(): Observable<Subdevice[]> {
    return this.adminService.listSubdevices();
  }
}
