import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { AuthenticationService } from '../../Authentication/authentication.service';
import { Location } from '@angular/common';
import { ScenarioService } from '../scenario.service';
import { ToolbarService } from '../anomaly-detector/new-scenario/toolbar.service';
import { Subscription } from 'rxjs';

@Component({
    selector: 'app-dashboard',
    imports: [CommonModule, RouterModule],
    templateUrl: './dashboard.component.html',
    styleUrl: './dashboard.component.css'
})
export class DashboardComponent {

  selectedOption: string = '';  
  saveButtonVisible: boolean = false;
  private toolbarSub: Subscription | null = null;
  
  constructor(
    private authenticationService: AuthenticationService,
    private router: Router,
    private location: Location,
    private scenarioDesign: ScenarioService,
    private toolbarService: ToolbarService,
  ) {}

  ngOnInit(): void {
    this.toolbarSub = this.toolbarService.saveButtonVisible$.subscribe(
      (visible) => {
        this.saveButtonVisible = visible;
      }
    );
  }

  navigateTo(path: string): void {
    this.selectedOption = path;  
    this.router.navigate([`/dashboard/${path}`]);
  }

  isSelected(option: string): boolean {
    return this.selectedOption === option;  
  }

  isDashboard(): boolean {
    return this.router.url === '/dashboard';
  }

  isNewScenario(): boolean {
    return this.router.url.includes('/anomaly-detector/new-scenario') || this.router.url.includes('/anomaly-detector/edit-scenario');
  }

  isEditScenario(): boolean {
    return this.router.url.includes('/anomaly-detector/edit-scenario');
  }

  isFinishedScenario(): boolean {
    return this.router.url.includes('production') || this.router.url.includes('timeline-ad') || this.router.url.includes('metrics');
  }

  async goBack(): Promise<void> {
    if (this.isNewScenario()) {
      const hasChanges = this.scenarioDesign.getUnsavedChanges();
      
      if (hasChanges) {
        const confirmSave = confirm('Do you want to save the scenario?');
        if (confirmSave) {
          await this.scenarioDesign.requestSave(); 
        }
      }
    }

    this.navigateBack();
  }

  private navigateBack() {
    const currentUrl = this.router.url;
    const urlParts = currentUrl.split('/');

    if (urlParts.length > 3) {
      if (this.isEditScenario() || this.isFinishedScenario()) {
        urlParts.pop();
      }
      urlParts.pop();
      const newUrl = urlParts.join('/');
      this.router.routeReuseStrategy.shouldReuseRoute = () => false;
      this.router.navigateByUrl(newUrl);
    } else {
      this.router.routeReuseStrategy.shouldReuseRoute = () => false;
      this.router.navigate(['/dashboard']);
      this.selectedOption = '';
    }
  }

  logout() {
    if (this.authenticationService.logout()) {
      alert('Logout correctly.');
      this.router.navigate(['/login']);
    }
  }

  onSaveClick(): void {
    this.toolbarService.triggerSave();
  }

  ngOnDestroy(): void {
    this.toolbarSub?.unsubscribe();
  }
}
