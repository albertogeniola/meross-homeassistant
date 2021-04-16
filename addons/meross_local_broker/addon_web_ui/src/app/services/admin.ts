import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Device, DeviceOnlineStatus } from '@app/model/device';
import { environment } from '@env/environment';
import { Observable, of } from 'rxjs';
import { catchError, tap, map } from 'rxjs/operators';

/**
 * Interface for ADMIN apis
 */
@Injectable({
  providedIn: 'root',
})
export class AdminService {
  constructor(private http: HttpClient) {}

  /**
   * Handle Http operation that failed.
   * Let the app continue.
   * @param operation - name of the operation that failed
   * @param result - optional value to return as the observable result
   */
  private handleError<T>(operation = 'operation', result?: T) {
    return (error: any): Observable<T> => {
      console.error(error); // log to console instead
      return of(result as T);
    };
  }

  updateDevice(uuid: string, devicePatch: any): Observable<Device> {
    var headers = new HttpHeaders();
    headers.append('Content-Type', 'application/json; charset=utf-8');
    return this.http
      .put<any>(environment.backend + '/_admin_/devices/' + uuid, devicePatch, { headers })
      .pipe(
        map((device) => {
          // Convert date
          device.last_seen_time = new Date(device.last_seen_time);
          return device as Device;
        }, catchError(this.handleError<Device>('updateDevice', null)))
      );
  }

  listDevices(): Observable<Device[]> {
    var headers = new HttpHeaders();
    headers.append('Content-Type', 'application/json; charset=utf-8');
    return this.http
      .get<any[]>(environment.backend + '/_admin_/devices', { headers })
      .pipe(
        map((devices) =>
          devices.map((device) => {
            // Convert date
            device.last_seen_time = new Date(device.last_seen_time);
            return device as Device;
          })
        ),
        catchError(this.handleError<Device[]>('listDevices', []))
      );
  }
}
