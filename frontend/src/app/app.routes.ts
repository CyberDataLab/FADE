import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { LoginComponent } from './Authentication/login/login.component';
import { RegisterComponent } from './Authentication/register/register.component';
import { DashboardComponent } from './Windows/dashboard/dashboard.component';
import { AnomalyDetectorComponent } from './Windows/anomaly-detector/anomaly-detector.component';
import { PoliciesComponent } from './Windows/policies/policies.component';
import { OptionsComponent } from './Windows/options/options.component';
import { UserComponent } from './Windows/user/user.component';
import { ResetPasswordComponent } from './Authentication/reset-password/reset-password.component';
import { SendEmailComponent } from './Authentication/send-email/send-email.component';
import { MetricsComponent } from './Windows/anomaly-detector/metrics/metrics.component';
import { TimelineADComponent } from './Windows/anomaly-detector/timeline-ad/timeline-ad.component';
import { NewScenarioComponent } from './Windows/anomaly-detector/new-scenario/new-scenario.component';
import { ProductionComponent } from './Windows/anomaly-detector/production/production.component';

export const routes: Routes = [
    { path: '', redirectTo: '/login', pathMatch: 'full'},
    { path: 'login', component: LoginComponent },
    { path: 'register', component: RegisterComponent },
    { path: 'dashboard', component: DashboardComponent, children: [
        { path: 'anomaly-detector', component: AnomalyDetectorComponent, children: [
            { path: ':id/timeline-ad', component: TimelineADComponent },
            { path: ':id/production', component: ProductionComponent },
            { path: ':id/metrics', component: MetricsComponent },
            { path: 'new-scenario', component: NewScenarioComponent },
            { path: 'edit-scenario/:id', component: NewScenarioComponent }

        ]},
        { path: 'policies', component: PoliciesComponent },
        { path: 'options', component: OptionsComponent },
        { path: 'user', component: UserComponent }
    ]},
    { path: 'reset-password', component: ResetPasswordComponent },
    { path: 'send-email', component: SendEmailComponent }
];


@NgModule({
imports: [RouterModule.forRoot(routes, {useHash: true})],
exports: [RouterModule]
})
export class AppRoutingModule { }