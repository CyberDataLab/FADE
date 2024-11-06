import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { LoginComponent } from './Authentication/login/login.component';
import { RegisterComponent } from './Authentication/register/register.component';
import { DashboardComponent } from './Windows/dashboard/dashboard.component';
import { AnomalyDetectorComponent } from './Windows/anomaly-detector/anomaly-detector.component';
import { XaiComponent } from './Windows/xai/xai.component';
import { PoliciesComponent } from './Windows/policies/policies.component';
import { OptionsComponent } from './Windows/options/options.component';
import { UserComponent } from './Windows/user/user.component';
import { ResetPasswordComponent } from './Authentication/reset-password/reset-password.component';
import { SendEmailComponent } from './Authentication/send-email/send-email.component';

export const routes: Routes = [
    { path: '', redirectTo: '/login', pathMatch: 'full'},
    { path: 'login', component: LoginComponent},
    { path: 'register', component: RegisterComponent},
    { path: 'dashboard', component: DashboardComponent},
    { path: 'anomaly_detector', component: AnomalyDetectorComponent},
    { path: 'xai', component: XaiComponent},
    { path: 'policies', component: PoliciesComponent},
    { path: 'options', component: OptionsComponent},
    { path: 'user', component: UserComponent},
    { path: 'reset-password', component: ResetPasswordComponent},
    { path: 'send-email', component: SendEmailComponent}
    
];

@NgModule({
imports: [RouterModule.forRoot(routes, {useHash: true})],
exports: [RouterModule]
})
export class AppRoutingModule { }