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

  constructor(private serviceStore: ServiceStore, private adminService: AdminService) {}

  ngOnInit(): void {
    // Update the services once
    this.serviceStore.services.subscribe((services) => (this.services = services));
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
