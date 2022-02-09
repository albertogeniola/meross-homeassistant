import { Component, OnInit } from '@angular/core';

@Component({
  selector: 'app-status',
  templateUrl: './status.component.html',
  styleUrls: ['./status.component.scss'],
})
export class StatusComponent implements OnInit {
  public processes: any = [
    { name: 'test', status: 'running' },
    { name: 'test', status: 'stopped' },
    { name: 'test', status: 'error' },
  ];

  constructor() {}

  ngOnInit(): void {}
}
