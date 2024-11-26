import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { AnomalyDetectorComponent } from '../anomaly-detector/anomaly-detector.component';
import { XaiComponent } from '../xai/xai.component';
import { PoliciesComponent } from '../policies/policies.component';
import { OptionsComponent } from '../options/options.component';
import { UserComponent } from '../user/user.component'
import { AuthenticationService } from '../../Authentication/authentication.service';
import { Location } from '@angular/common';
import { DataSourceComponent } from '../anomaly-detector/new-scenario/data-source/data-source.component';
import { DataProcessingComponent } from '../anomaly-detector/new-scenario/data-processing/data-processing.component';
import { FeatureEngineeringComponent } from '../anomaly-detector/new-scenario/feature-engineering/feature-engineering.component';
import { ModelSelectionComponent } from '../anomaly-detector/new-scenario/model-selection/model-selection.component';
import { ModelTrainingComponent } from '../anomaly-detector/new-scenario/model-training/model-training.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule,
    RouterModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent {

  selectedOptionDropdown: string = '';
  
  constructor(
    private authenticationService: AuthenticationService,
    private router: Router,
    private location: Location
  ) {}

  navigateTo(path: string): void {
    this.router.navigate([`/dashboard/${path}`]);
  }
  navigateToNewScenario(path: string): void {
    this.router.navigate([`/dashboard/anomaly-detector/new-scenario/${path}`]);
  }

  isDashboard(): boolean {
    return this.router.url === '/dashboard';
  }

  isNewScenario(): boolean {
    return this.router.url.includes('/anomaly-detector/new-scenario');
  }

  goBack(): void {
    const currentUrl = this.router.url;
    const urlParts = currentUrl.split('/');

    if (urlParts.length > 3) {
      urlParts.pop(); 
      const newUrl = urlParts.join('/'); 
      this.router.navigateByUrl(newUrl); 
    } else {
      this.router.navigate(['/dashboard']);
    }
  }

  onDropdownChange(): void {
    if (this.selectedOptionDropdown === 'new') {
      this.navigateTo('anomaly-detector/new-scenario');
    } else if (this.selectedOptionDropdown === 'import') {
      this.navigateTo('anomaly-detector/import-scenario');
    }
  }

  logout() {
    if (this.authenticationService.logout()) {
      alert('Logout correctly.');
      this.router.navigate(['/login']);
    }
  }

}