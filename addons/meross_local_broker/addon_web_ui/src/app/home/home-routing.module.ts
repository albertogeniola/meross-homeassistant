import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { marker } from '@biesbjerg/ngx-translate-extract-marker';
import { HomeComponent } from './home.component';
import { StatusComponent } from '../status/status.component';
import { ConfigurationComponent } from '../configuration/configuration.component';
import { Shell } from '@app/shell/shell.service';
import { WizardComponent } from '@app/wizard/wizard.component';

const routes: Routes = [
  Shell.childRoutes([
    { path: '', redirectTo: '/home', pathMatch: 'full' },
    { path: 'home', component: HomeComponent, data: { title: marker('Home') } },
    { path: 'status', component: StatusComponent, data: { title: marker('Status') } },
    { path: 'configuration', component: ConfigurationComponent, data: { title: marker('Configuration') } },
    { path: 'wizard', component: WizardComponent, data: { title: marker('Wizard') } },
  ]),
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
  providers: [],
})
export class HomeRoutingModule {}
