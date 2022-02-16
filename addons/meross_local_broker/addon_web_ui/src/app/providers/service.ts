import { Injectable } from '@angular/core';
import { ServiceStatus } from '@app/model/service';
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
export class ServiceStore {
  // Internal service handler
  private _services: BehaviorSubject<ServiceStatus[]> = new BehaviorSubject([]);
  private REFRESH_TIME: number = 10000;

  // Exposed observable
  public readonly services: Observable<ServiceStatus[]> = this._services.asObservable();
  public readonly serviceUpdates: Observable<ServiceStatus[]> = interval(this.REFRESH_TIME).pipe(
    switchMap(() => this.serviceUpdate()),
    //takeUntil(this.reload$),
    share()
  );

  constructor(private adminService: AdminService) {
    // Perform a first poll
    this.serviceUpdate()
      .pipe(tap((e) => console.log(e)))
      .subscribe((services) => this._services.next(services));
  }

  private serviceUpdate(): Observable<ServiceStatus[]> {
    return this.adminService.listServices();
  }
}
