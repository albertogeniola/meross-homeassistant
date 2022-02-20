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
  // Internal handlers
  private _services: BehaviorSubject<ServiceStatus[]> = new BehaviorSubject([]);
  private _logSubjects: Map<string, BehaviorSubject<string[]>> = new Map<string, BehaviorSubject<string[]>>();
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
    this.serviceUpdate().subscribe((services) => this._services.next(services));
  }

  private serviceUpdate(): Observable<ServiceStatus[]> {
    return this.adminService.listServices();
  }

  private fetchServiceLogs(serviceName: string): Observable<string[]> {
    return this.adminService.getServiceLog(serviceName);
  }

  /**
   * Subscribes to the logs of a given service.
   * @param serviceName
   */
  public followServiceLogs(serviceName: string): Observable<string[]> {
    // We hold a BehaviorSubbject for every serviceName.
    // Every time a new subscriber wants to consume logs for a specific
    // service, we build/retrieve the appropriate BehaviorSubject
    // and start the polling.
    let subject = this._logSubjects.get(serviceName);
    if (!subject) {
      // Create the behavior subject
      subject = new BehaviorSubject([]);

      // Setup the interval updater
      interval(this.REFRESH_TIME).subscribe(() =>
        this.fetchServiceLogs(serviceName).subscribe((logLines) => subject.next(logLines))
      );

      // Get initial data and fill the subject
      this.fetchServiceLogs(serviceName).subscribe((logLines) => subject.next(logLines));

      this._logSubjects[serviceName] = subject;
    }

    // In case the subject already exists, return it directly.
    return subject.asObservable();
  }
}
