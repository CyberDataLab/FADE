// Angular core and common modules
import { Component, ViewChild, ElementRef, Inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PLATFORM_ID } from '@angular/core';
import { HttpClient } from '@angular/common/http';

// Application-specific imports
import { ScenarioService } from '../scenario.service';
import { Scenario } from '../../DTOs/Scenario';

/**
 * @summary Manages the main view for anomaly detection scenarios.
 * 
 * This component supports importing, listing, deleting, editing, running, and navigating
 * between anomaly detection scenarios. It also supports CSV/PCAP file validation and uses
 * config-driven model type classification.
 */
@Component({
    selector: 'app-anomaly-detector',
    imports: [
        CommonModule,
        FormsModule,
        RouterModule
    ],
    templateUrl: './anomaly-detector.component.html',
    styleUrl: './anomaly-detector.component.css'
})

export class AnomalyDetectorComponent {

  /** @summary List of scenarios loaded from backend */
  scenarios: Scenario[] = [];

  /** @summary Model type classification from config file */
  private modelTypes: {
    classification: string[],
    regression: string[],
    anomalyDetection: string[]
  } = { classification: [], regression: [], anomalyDetection: [] };
  
  /** @summary Reference to file input element for importing scenarios */
  @ViewChild('fileInput') fileInputRef!: ElementRef;

/**
   * @summary Initializes the component with injected Angular services.
   * 
   * Injects platform information, router for navigation, HTTP client for config loading,
   * and a custom ScenarioService for backend operations.
   * 
   * @param platformId Angular token to detect browser/server environment
   * @param router Used to navigate between views within the dashboard
   * @param scenarioService Custom service to manage scenario-related API calls
   * @param http Used to load static config files (like config.json)
   */
  constructor(
    @Inject(PLATFORM_ID) private platformId: Object,
    private router: Router,
    private scenarioService: ScenarioService,
    private http: HttpClient
  ) {}
  
  /**
   * @summary Initializes the component and loads scenarios and config.
   */
  ngOnInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      const tableBody = document.querySelector('.scenario-table tbody');

      // Enable horizontal scrolling for the table on mouse wheel
      if (tableBody) {
        tableBody.addEventListener('wheel', (e: Event) => {
          const wheelEvent = e as WheelEvent; 
          tableBody.scrollTop += wheelEvent.deltaY;
          e.preventDefault(); 
        }, { passive: false });
      }
    }

    // Load model type config and fetch scenarios
    this.loadConfig();
    this.getScenarios(); 
  }
  
  /**
   * @summary Loads model type definitions from `config.json`.
   */
  private loadConfig(): void {
    this.http.get('assets/config.json').subscribe({
      next: (config: any) => {
        this.modelTypes.classification = config.sections.dataModel.classification.map((m: any) => m.type);
        this.modelTypes.regression = config.sections.dataModel.regression.map((m: any) => m.type);
        this.modelTypes.anomalyDetection = config.sections.dataModel.anomalyDetection.map((m: any) => m.type);
      },
      error: (err:any) => console.error('Error loading config:', err)
    });
  }

  /**
   * @summary Navigates to a given anomaly detector sub-route.
   * 
   * @param path Path to append to the base route
   */
  navigateTo(path: string): void {
    this.router.navigate([`/dashboard/anomaly-detector/${path}`]);
  }

  /**
   * @summary Checks if the current route is exactly the root anomaly detector view.
   * 
   * @returns True if current route is root
   */
  isRootSubRoute(): boolean {
    return this.router.isActive('/dashboard/anomaly-detector', true); 
  }

  /**
   * @summary Navigates to the new scenario creation page.
   */
  newScenario(): void {
    this.router.navigate(['/dashboard/anomaly-detector/new-scenario']);
  }

  /**
   * @summary Triggers the hidden file input for importing a scenario.
   */
  triggerFileInput(): void {
    const fileInput = document.getElementById('fileInput') as HTMLInputElement;
    if (fileInput) {
      fileInput.click();
    }
  }

  /**
   * @summary Loads a scenario JSON and its corresponding data files.
   * 
   * This function validates the selected JSON structure, ensures all required
   * CSV and PCAP files are provided, and then saves the scenario via backend.
   * 
   * @param event File input change event
   */
  async loadScenario(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
  
    if (input?.files?.length) {
      const files = Array.from(input.files);
      const jsonFile = files.find(file => file.name.endsWith('.json'));
      const csvFiles = files.filter(file => file.name.endsWith('.csv'));
      const networkFiles = files.filter(file => file.name.endsWith('.pcap'));
  
      if (!jsonFile) {
        alert('A JSON file must be selected.');
        return;
      }
  
      const reader = new FileReader();
  
      // Read and parse the JSON file
      reader.onload = async (e: ProgressEvent<FileReader>) => {
        try {

          // Extract expected filenames
          const design = JSON.parse(e.target?.result as string);
  
          const csvElements = design.elements.filter((el: any) => el.type === "CSV");
          const networkElements = design.elements.filter((el: any) => el.type === "Network");
  
          const expectedCsvNames = csvElements.map((el: any) => el.parameters?.csvFileName).filter(Boolean);
          const expectedNetworkNames = networkElements.map((el: any) => el.parameters?.networkFileName).filter(Boolean);
  
          const missingCsv = expectedCsvNames.filter((name: string) => !csvFiles.some(file => file.name === name));
          const missingPcap = expectedNetworkNames.filter((name: string) => !networkFiles.some(file => file.name === name));
  
          // Match files by name
          const matchedCsvFiles = expectedCsvNames.map((name: string) => csvFiles.find(f => f.name === name)!);
          const matchedNetworkFiles = expectedNetworkNames.map((name: string) => networkFiles.find(f => f.name === name)!);
  
          const scenarioName = jsonFile.name.substring(0, jsonFile.name.lastIndexOf('.'));
  
          // Save scenario
          this.scenarioService.saveScenario(scenarioName, design, matchedCsvFiles, matchedNetworkFiles)
            .subscribe({
              next: () => {
                this.getScenarios();
                alert('Scenario successfully imported.');
              },
              error: () => {
                alert('Unexpected error while importing the scenario.');
              }
            });
  
        } catch (err) {
          alert('Error loading the scenario. Invalid format.');
        }
      };
  
      reader.readAsText(jsonFile);
    }
  
    input.value = '';
  }

  /**
   * @summary Navigates to the TimelineAD view for a specific scenario.
   * 
   * @param uuid UUID of the selected scenario
   */
  viewTimelineAD(uuid: string) {
    this.router.navigate([`/dashboard/anomaly-detector/${uuid}/timeline-ad`]);
  }

  /**
   * @summary Navigates to the Metrics view for a specific scenario.
   * 
   * @param uuid UUID of the selected scenario
   */
  viewMetrics(uuid: string) {
    this.router.navigate([`/dashboard/anomaly-detector/${uuid}/metrics`]);
  }

  /**
   * @summary Navigates to the Production view for a specific scenario.
   * 
   * @param uuid UUID of the selected scenario
   */
  production(uuid: string) {
    this.router.navigate([`/dashboard/anomaly-detector/${uuid}/production`]);
  }

  /**
   * @summary Checks if a scenario contains any classification or regression models.
   * 
   * @param scenario Scenario object with a design definition
   * @returns True if at least one model of type classification or regression is present
   */
  hasClassificationOrRegression(scenario: Scenario): boolean {
    const design = typeof scenario.design === 'string' ? 
                  JSON.parse(scenario.design) : 
                  scenario.design;
    return design.elements?.some((el: any) => 
      this.modelTypes.classification.includes(el.type) || 
      this.modelTypes.regression.includes(el.type)
    );
  }
  
  /**
   * @summary Checks if a scenario contains any anomaly detection models.
   * 
   * @param scenario Scenario object with a design definition
   * @returns True if at least one anomaly detection model is present
   */
  hasAnomalyDetection(scenario: Scenario): boolean {
    const design = typeof scenario.design === 'string' ? 
                  JSON.parse(scenario.design) : 
                  scenario.design;
    return design.elements?.some((el: any) => 
      this.modelTypes.anomalyDetection.includes(el.type)
    );
  }
  
  /**
   * @summary Retrieves all scenarios from the backend and sorts them by date.
   */
  getScenarios(): void {
    this.scenarioService.getScenarios().subscribe(
      (response: Scenario[]) => {
        // Normalize and map scenarios into expected structure
        this.scenarios = response.map(scenarioData => {
          return {
            id: scenarioData.id,
            name: scenarioData.name,
            design: scenarioData.design,
            uuid: scenarioData.uuid,
            status: scenarioData.status,
            date: scenarioData.date,
          };
        });

        // Sort scenarios by descending date
        this.sortScenariosByDate();
      },
      (error: any) => {
        console.error('Error getting scenarios:', error);
      }
    );
  }

  /**
   * @summary Sorts the current scenario list by date, newest first.
   */
  sortScenariosByDate() {
    this.scenarios.sort((a, b) => {
      const dateA = new Date(a.date).getTime();
      const dateB = new Date(b.date).getTime();
      return dateB - dateA; 
    });
  }

  /**
   * @summary Deletes a scenario after user confirmation.
   * 
   * @param uuid UUID of the scenario to delete
   */
  deleteScenario(uuid: string): void {
    if (confirm('Are you sure you want to delete this scenario?')) {
      this.scenarioService.deleteScenario(uuid).subscribe({
        next: () => {
          this.getScenarios();
          alert('Scenario deleted successfully');
        },
        error: (error: any) => {
          console.error('Error deleting scenario:', error);
          alert('Error deleting scenario');
        }
      });
    }
  }

  /**
   * @summary Navigates to the edit view for a given scenario.
   * 
   * @param uuid UUID of the scenario to edit
   */
  editScenario(uuid: string): void {
    this.router.navigate([`/dashboard/anomaly-detector/edit-scenario/${uuid}`]);
  }

  /**
   * @summary Executes a scenario if it is not already running.
   * 
   * @param status Current status of the scenario (e.g., 'Running')
   * @param uuid UUID of the scenario to run
   */
  runScenario(status: string, uuid: string): void {
    if (status == 'Running') {
      alert("Scenario running. Wait for the scenario to finish before running it again.");
    }
    
    if (confirm('Are you sure you want to run this scenario?')) {
      this.scenarioService.runScenario(uuid).subscribe({
        next: (response:any) => {
          alert('Scenario running successfully');
          this.getScenarios();
  
          const metrics = response.metrics;
        },
        error: (error: any) => {
          console.error('Error running scenario:', error);
          const errorMsg = error?.error?.error || 'Unexpected error';
          alert('Error running scenario: ' + JSON.stringify(errorMsg));
          this.getScenarios();
        }
      });
    }
  }

  /**
   * @summary Downloads the scenario design as a `.json` file.
   * 
   * @param scenario The scenario object to export
   */
  downloadScenario(scenario: any) {
    const design = typeof scenario.design === 'string' 
        ? JSON.parse(scenario.design) 
        : scenario.design;

    const formattedJson = JSON.stringify(design, null, 2); 
    const blob = new Blob([formattedJson], { type: 'application/json' });
    
    const link = document.createElement('a');
    const fileName = `${scenario.name}.json`;
    
    // Create and trigger the download link
    link.href = URL.createObjectURL(blob);
    link.download = fileName;
    
    document.body.appendChild(link); 
    link.click();
    document.body.removeChild(link); 
    
    URL.revokeObjectURL(link.href);
  }
}
