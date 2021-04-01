import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Device } from '@app/model/device';
import { environment } from '@env/environment';
import { Observable, of } from 'rxjs';
import { catchError, tap } from 'rxjs/operators';

/**
 * Interface for ADMIN apis
 */
@Injectable({
    providedIn: 'root'
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

    listDevices(): Observable<Device[]> {
        var headers = new HttpHeaders();
        headers.append('Content-Type', 'application/json; charset=utf-8');
        return this.http.get<Device[]>(environment.backend + '/_admin_/devices', {headers})
            .pipe(
                catchError(this.handleError<Device[]>('listDevices', []))
            );
    }
}