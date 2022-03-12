import { Component, OnInit } from '@angular/core';
import { NgxQrcodeElementTypes, NgxQrcodeErrorCorrectionLevels } from '@techiediaries/ngx-qrcode';

@Component({
  selector: 'app-configuration',
  templateUrl: './configuration.component.html',
  styleUrls: ['./configuration.component.scss'],
})
export class ConfigurationComponent implements OnInit {
  public hidePassword: boolean = true;
  public accountEmail: string = null;
  public accountPassword: string = null;
  public enableMerossLink: boolean = false;
  public processing: boolean = false;

  public elementType = NgxQrcodeElementTypes.IMG;
  public correctionLevel = NgxQrcodeErrorCorrectionLevels.MEDIUM;
  public encodedAccountLoginData: string = null;

  constructor() {}

  ngOnInit(): void {}

  saveAccountData() {
    let data = {
      email: this.accountEmail,
      password: this.accountPassword,
      enableMerossLink: this.enableMerossLink,
    };
    let strdata = JSON.stringify(data);
    this.encodedAccountLoginData = btoa(strdata);
  }
}
