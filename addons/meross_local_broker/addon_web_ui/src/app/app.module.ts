import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { TranslateModule } from '@ngx-translate/core';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { MaterialModule } from './material.module';

import { CoreModule } from '@core';
import { SharedModule } from '@shared';
import { HomeModule } from './home/home.module';
import { ShellModule } from './shell/shell.module';
import { AboutModule } from './about/about.module';
import { AppComponent } from './app.component';
import { AppRoutingModule } from './app-routing.module';
import { AnsiparserPipe } from './ansiparser.pipe';
import { StatusComponent } from './status/status.component';
import { AccountComponent } from './configuration/account.component';
import { NgxQRCodeModule } from '@techiediaries/ngx-qrcode';
import { ConfigurationComponent } from './configuration/configuration.component';
import { WizardComponent } from './wizard/wizard.component';

@NgModule({
  imports: [
    BrowserModule,
    FormsModule,
    HttpClientModule,
    TranslateModule.forRoot(),
    BrowserAnimationsModule,
    MaterialModule,
    CoreModule,
    SharedModule,
    ShellModule,
    HomeModule,
    AboutModule,
    NgxQRCodeModule,
    AppRoutingModule,
  ],
  declarations: [
    AppComponent,
    AnsiparserPipe,
    StatusComponent,
    AccountComponent,
    ConfigurationComponent,
    WizardComponent,
  ],
  providers: [],
  bootstrap: [AppComponent],
})
export class AppModule {}
