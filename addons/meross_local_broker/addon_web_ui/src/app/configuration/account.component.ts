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
    password: ['', Validators.required],
    enableMerossLink: [false],
  });

  public hidePassword: boolean = true;
  public processing: boolean = false;

  public elementType = NgxQrcodeElementTypes.IMG;
  public correctionLevel = NgxQrcodeErrorCorrectionLevels.MEDIUM;
  public encodedAccountLoginData: string = null;
  public reconfigureAccount: boolean = false;

  public configuredAccount: User = null;

  constructor(private fb: FormBuilder, private adminService: AdminService) {}

  private loadAccount(account: User | null) {
    if (!account) {
      this.configuredAccount = null;
      this.reconfigureAccount = true;
    } else {
      // Fetch configured data
      this.configuredAccount = account;
      this.accountForm.controls.password.setValue(null);
      this.accountForm.controls.email.setValue(account.email);
      this.accountForm.controls.enableMerossLink.setValue(account.enable_meross_link);
    }
  }

  ngOnInit(): void {
    this.adminService.getAccountConfiguration().subscribe((account: User) => {
      this.loadAccount(account);
    });
  }

  editConfiguration(reconfigure: boolean): void {
    if (reconfigure) {
      this.adminService.getAccountConfiguration().subscribe((account: User) => {
        this.loadAccount(account);
      });
    }
    this.reconfigureAccount = reconfigure;
  }

  onSubmit(): void {
    this.processing = true;
    this.adminService
      .updateAccountConfiguration(
        this.accountForm.controls.email.value,
        this.accountForm.controls.password.value,
        this.accountForm.controls.enableMerossLink.value
      )
      .subscribe((account: User) => {
        this.processing = false;
        this.loadAccount(account);
        this.editConfiguration(false);
      });

    /*
    let strdata = JSON.stringify(data);
    this.encodedAccountLoginData = btoa(strdata);
    */
  }
}
