// Angular core and common modules
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule, NavigationEnd } from '@angular/router';
import { filter, Subscription } from 'rxjs';

// Application-specific services
import { AuthenticationService } from '../../Authentication/authentication.service';
import { ScenarioService } from '../scenario.service';
import { ToolbarService } from '../anomaly-detector/new-scenario/toolbar.service';

/**
 * @summary Main dashboard container for routing and state management.
 * 
 * This component manages the dashboard view, tracks navigation events,
 * handles route-based state, and manages save logic and logout behavior.
 */
@Component({
    selector: 'app-dashboard',
    imports: [CommonModule, RouterModule],
    templateUrl: './dashboard.component.html',
    styleUrl: './dashboard.component.css'
})
export class DashboardComponent {

  /** @summary Tracks the current selected dashboard section */
  selectedOption: string = '';  

  /** @summary Indicates whether the save button should be shown */
  saveButtonVisible: boolean = false;

  /** @summary Subscription to the toolbar save button visibility */
  private toolbarSub: Subscription | null = null;
  
  /**
   * @summary Injects router, services, and handles toolbar and navigation.
   * 
   * @param authenticationService Handles session and logout
   * @param router Used for navigation tracking and redirection
   * @param scenarioDesign Service that tracks scenario save state
   * @param toolbarService Service to control the save button
   */
  constructor(
    private authenticationService: AuthenticationService,
    private router: Router,
    private scenarioDesign: ScenarioService,
    private toolbarService: ToolbarService,
  ) {}

  /**
   * @summary Initializes state, subscribes to toolbar visibility, and tracks navigation.
   */
  ngOnInit(): void {
    // Subscribe to visibility changes of the save button
    this.toolbarSub = this.toolbarService.saveButtonVisible$.subscribe(
      (visible) => {
        this.saveButtonVisible = visible;
      }
    );
  
    // Set selected option based on the current URL
    this.updateSelectedOptionFromUrl(this.router.url);
  
    // Update selected option whenever navigation ends
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: NavigationEnd) => {
      this.updateSelectedOptionFromUrl(event.urlAfterRedirects);
    });
  }
  
  /**
   * @summary Parses the current URL to determine selected dashboard section.
   * 
   * @param url Full navigation URL
   */
  private updateSelectedOptionFromUrl(url: string): void {
    const parts = url.split('/');
    const index = parts.indexOf('dashboard');
    if (index >= 0 && parts.length > index + 1) {
      this.selectedOption = parts[index + 1];
    } else {
      this.selectedOption = '';
    }
  }

  /**
   * @summary Navigates to a dashboard subpath and updates selection.
   * 
   * @param path Relative dashboard route (e.g., "anomaly-detector")
   */
  navigateTo(path: string): void {
    this.selectedOption = path;  
    this.router.navigate([`/dashboard/${path}`]);
  }

  /**
   * @summary Checks if a given option is the current selected one.
   * 
   * @param option Section name to compare
   * @returns True if selected
   */
  isSelected(option: string): boolean {
    return this.selectedOption === option;  
  }

  /**
   * @summary Checks if the current view is the main dashboard view.
   */
  isDashboard(): boolean {
    return this.router.url === '/dashboard';
  }

  /**
   * @summary Determines if the user is editing or creating a new scenario.
   */
  isNewScenario(): boolean {
    return this.router.url.includes('/anomaly-detector/new-scenario') || 
           this.router.url.includes('/anomaly-detector/edit-scenario');
  }

  /**
   * @summary Determines if the user is editing an existing scenario.
   */
  isEditScenario(): boolean {
    return this.router.url.includes('/anomaly-detector/edit-scenario');
  }

  /**
   * @summary Determines if the user is viewing a finished or post-processing scenario.
   */
  isFinishedScenario(): boolean {
    return this.router.url.includes('production') || 
           this.router.url.includes('timeline-ad') || 
           this.router.url.includes('metrics');
  }

  /**
   * @summary Handles back navigation and prompts user to save scenario if needed.
   */
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

  /**
   * @summary Handles logic to compute and navigate to the previous URL.
   */
  private navigateBack() {
    const currentUrl = this.router.url;
    const urlParts = currentUrl.split('/');

    // For deeper routes, remove last segments
    if (urlParts.length > 3) {
      if (this.isEditScenario() || this.isFinishedScenario()) {
        urlParts.pop();
      }
      urlParts.pop();
      const newUrl = urlParts.join('/');
      this.router.routeReuseStrategy.shouldReuseRoute = () => false;
      this.router.navigateByUrl(newUrl);
    } else {
      // Default fallback to main dashboard
      this.router.routeReuseStrategy.shouldReuseRoute = () => false;
      this.router.navigate(['/dashboard']);
      this.selectedOption = '';
    }
  }

  /**
   * @summary Logs the user out and navigates back to login page.
   */
  logout() {
    if (this.authenticationService.logout()) {
      alert('Logout correctly.');
      this.router.navigate(['/login']);
    }
  }

  /**
   * @summary Triggers save event via toolbar service.
   */
  onSaveClick(): void {
    this.toolbarService.triggerSave();
  }

  /**
   * @summary Cleans up subscriptions on component destroy.
   */
  ngOnDestroy(): void {
    this.toolbarSub?.unsubscribe();
  }
}
