import { Component, OnInit } from '@angular/core';
import { ServiceStatus } from '@app/model/service';
import { ServiceStore } from '@app/providers/service';
import { AdminService } from '@app/services/admin';

@Component({
  selector: 'app-status',
  templateUrl: './status.component.html',
  styleUrls: ['./status.component.scss'],
})
export class StatusComponent implements OnInit {
  public services: ServiceStatus[] = [];
  public serviceNames: string[] = [];
  public logs: Map<string, string[]> = new Map();

  constructor(private serviceStore: ServiceStore, private adminService: AdminService) {}

  ngOnInit(): void {
    // Update the services once and make sure to subscribe to all the services
    this.serviceStore.services.subscribe((services) => {
      this.services = services;
      for (let service of this.services) {
        this.serviceNames.push(service.name);
        this.serviceStore.followServiceLogs(service.name).subscribe((lines) => {
          this.logs[service.name] = lines.reverse();
        });
      }
    });
    this.serviceStore.serviceUpdates.subscribe((services) => {
      this.services = services;
      this.serviceNames = [];
      for (let s of services) {
        this.serviceNames.push(s.name);
      }
    });
  }

  stopService(serviceName: string): void {
    this.adminService.stopService(serviceName).subscribe((res) => console.log(res));
  }

  startService(serviceName: string): void {
    this.adminService.startService(serviceName).subscribe((res) => console.log(res));
  }

  restartService(serviceName: string): void {
    this.adminService.restartService(serviceName).subscribe((res) => console.log(res));
  }
}
