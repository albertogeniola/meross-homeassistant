import { Component, OnInit } from '@angular/core';
import { NgxQrcodeElementTypes, NgxQrcodeErrorCorrectionLevels } from '@techiediaries/ngx-qrcode';
import { AdminService } from '@app/services/admin';
import { User } from '@app/model/user';
import { FormGroup, FormControl } from '@angular/forms';
import { FormBuilder } from '@angular/forms';
import { Validators } from '@angular/forms';

@Component({
  selector: 'configuration-account',
  templateUrl: './account.component.html',
  styleUrls: ['./account.component.scss'],
})
export class AccountComponent implements OnInit {
  accountForm = this.fb.group({
    email: ['', Validators.required],
    password: [''],
    enableMerossLink: [''],
  });

  public hidePassword: boolean = true;
  public processing: boolean = false;

  public elementType = NgxQrcodeElementTypes.IMG;
  public correctionLevel = NgxQrcodeErrorCorrectionLevels.MEDIUM;
  public encodedAccountLoginData: string = null;

  public configuredAccount: User = null;

  constructor(private fb: FormBuilder, private adminService: AdminService) {}

  ngOnInit(): void {
    this.adminService.getAccountConfiguration().subscribe((account) => {
      if (!account) {
        this.configuredAccount = null;
      } else {
        // Fetch configured data
        this.configuredAccount = account;
        this.accountForm.controls.email.setValue(account.email);
        this.accountForm.controls.enableMerossLink.setValue(account.enable_meross_link);
      }
    });
  }

  changed(): boolean {
    return (
      this.configuredAccount.email != this.accountForm.controls.email.value ||
      this.configuredAccount.enable_meross_link != this.accountForm.controls.enableMerossLink.value
    );
  }

  updateAccountData() {
    /*
    let data = {
      email: this.accountEmail,
      password: this.accountPassword,
      enableMerossLink: this.enableMerossLink,
    };
    let strdata = JSON.stringify(data);
    this.encodedAccountLoginData = btoa(strdata);
    */
  }

  onSubmit() {}
}
