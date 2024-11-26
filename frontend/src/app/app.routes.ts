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
import { FeaturesComponent } from './Windows/anomaly-detector/features/features.component';
import { MetricsComponent } from './Windows/anomaly-detector/metrics/metrics.component';
import { TimelineADComponent } from './Windows/anomaly-detector/timeline-ad/timeline-ad.component';
import { NewScenarioComponent } from './Windows/anomaly-detector/new-scenario/new-scenario.component';
import { ImportScenarioComponent } from './Windows/anomaly-detector/import-scenario/import-scenario.component';
import { DataSourceComponent } from './Windows/anomaly-detector/new-scenario/data-source/data-source.component';
import { DataProcessingComponent } from './Windows/anomaly-detector/new-scenario/data-processing/data-processing.component';
import { FeatureEngineeringComponent } from './Windows/anomaly-detector/new-scenario/feature-engineering/feature-engineering.component';
import { ModelSelectionComponent } from './Windows/anomaly-detector/new-scenario/model-selection/model-selection.component';
import { ModelTrainingComponent } from './Windows/anomaly-detector/new-scenario/model-training/model-training.component';

export const routes: Routes = [
    { path: '', redirectTo: '/login', pathMatch: 'full'},
    { path: 'login', component: LoginComponent },
    { path: 'register', component: RegisterComponent },
    { path: 'dashboard', component: DashboardComponent, children: [
        { path: 'anomaly-detector', component: AnomalyDetectorComponent, children: [
            { path: 'features', component: FeaturesComponent },
            { path: 'timeline-ad', component: TimelineADComponent },
            { path: 'metrics', component: MetricsComponent },
            { path: 'new-scenario', component: NewScenarioComponent, children: [
                { path: 'data-source', component: DataSourceComponent },
                { path: 'data-processing', component: DataProcessingComponent },
                { path: 'feature-engineering', component: FeatureEngineeringComponent },
                { path: 'model-selection', component: ModelSelectionComponent },
                { path: 'model-training', component: ModelTrainingComponent }
            ] },
            { path: 'import-scenario', component: ImportScenarioComponent }

        ]},
        { path: 'xai', component: XaiComponent },
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