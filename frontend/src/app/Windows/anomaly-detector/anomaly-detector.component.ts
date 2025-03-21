import { Component, ViewChild, ElementRef, Inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FeaturesComponent } from './features/features.component';
import { Router } from '@angular/router';
import { TimelineADComponent } from './timeline-ad/timeline-ad.component';
import { MetricsComponent } from './metrics/metrics.component';
import { FormsModule } from '@angular/forms';
import { ScenarioService } from '../scenario.service';
import { Scenario } from '../../DTOs/Scenario';
import { PLATFORM_ID } from '@angular/core';

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
  scenarios: Scenario[] = [];

  @ViewChild('fileInput') fileInputRef!: ElementRef;

  constructor(@Inject(PLATFORM_ID) private platformId: Object, private router: Router, private scenarioService: ScenarioService) {}

  ngOnInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      const tableBody = document.querySelector('.scenario-table tbody');
      
      if (tableBody) {
        tableBody.addEventListener('wheel', (e: Event) => {
          const wheelEvent = e as WheelEvent; 
          tableBody.scrollTop += wheelEvent.deltaY;
          e.preventDefault(); 
        }, { passive: false });
      }
    }
    this.getScenarios();  
    this.scenarios.sort((a, b) => {
      const dateA = new Date(a.date).getTime();
      const dateB = new Date(b.date).getTime();
      return dateA - dateB; 
    });
  }
  

  navigateTo(path: string): void {
    this.router.navigate([`/dashboard/anomaly-detector/${path}`]);
  }

  isRootSubRoute(): boolean {
    return this.router.isActive('/dashboard/anomaly-detector', true); 
  }

  newScenario(): void {
    this.router.navigate(['/dashboard/anomaly-detector/new-scenario']);
  }


  triggerFileInput(): void {
    const fileInput = document.getElementById('fileInput') as HTMLInputElement;
    if (fileInput) {
      fileInput.click();
    }
  }

  async loadScenario(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
  
    if (input?.files?.length) {
      const files = Array.from(input.files);
      const jsonFile = files.find(file => file.name.endsWith('.json'));
      const csvFile = files.find(file => file.name.endsWith('.csv'));
  
      if (!jsonFile) {
        alert('A JSON file must be selected.');
        return;
      }
  
      const reader = new FileReader();
  
      reader.onload = async (e: ProgressEvent<FileReader>) => {
        try {
          const design = JSON.parse(e.target?.result as string);
          const csvElements = design.elements.filter((el: any) => el.type === "CSV");
          const expectedCsvName = design.elements.find((el: any) => el.type === "CSV")?.parameters?.csvFileName;
          /*
          if (!expectedCsvName) {
            alert('El JSON no contiene una referencia a un archivo CSV.');
            return;
          }
          */
          if (csvElements.length > 0) {
            if (!csvFile) {
                alert(`The corresponding CSV file must be selected: ${expectedCsvName}`);
                return;
            }

            if (csvFile.name !== expectedCsvName) {
                alert(`The name of the selected CSV file (${csvFile.name}) does not match the expected name (${expectedCsvName}).`);
                return;
            }
          }
    
          const scenarioName = jsonFile.name.substring(0, jsonFile.name.lastIndexOf('.'));

          this.scenarioService.saveScenario(scenarioName, design, csvFile)
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

  viewFeatures(uuid: string) {
    this.router.navigate([`/dashboard/anomaly-detector/${uuid}/features`]);
  }

  viewTimelineAD(uuid: string) {
    this.router.navigate([`/dashboard/anomaly-detector/${uuid}/timeline-ad`]);
  }

  viewMetrics(uuid: string) {
    this.router.navigate([`/dashboard/anomaly-detector/${uuid}/metrics`]);
  }
  
  
  getScenarios(): void {
    this.scenarioService.getScenarios().subscribe(
      (response: Scenario[]) => {
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

        this.sortScenariosByDate();
      },
      (error: any) => {
        console.error('Error getting scenarios:', error);
      }
    );
  }

  sortScenariosByDate() {
    this.scenarios.sort((a, b) => {
      const dateA = new Date(a.date).getTime();
      const dateB = new Date(b.date).getTime();
      return dateB - dateA; 
    });
  }

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

  editScenario(uuid: string): void {
    this.router.navigate([`/dashboard/anomaly-detector/edit-scenario/${uuid}`]);
  }

  runScenario(status: string, uuid: string): void {
    if (status == 'Running') {
      alert("Scenario running. Wait for the scenario to finish before running it again.");
    }
    
    if (confirm('Are you sure you want to run this scenario?')) {
      this.scenarioService.runScenario(uuid).subscribe({
        next: (response:any) => {
          alert('Scenario running successfully');
  
          const metrics = response.metrics;
        },
        error: (error: any) => {
          console.error('Error running scenario:', error);
          alert('Error running scenario');
        }
      });
    }
  }

  downloadScenario(scenario: any) {
    // Si scenario.design es una cadena, conviértela a objeto
    const design = typeof scenario.design === 'string' 
        ? JSON.parse(scenario.design) 
        : scenario.design;

    const formattedJson = JSON.stringify(design, null, 2); // Ahora sí tendrá formato
    const blob = new Blob([formattedJson], { type: 'application/json' });
    
    const link = document.createElement('a');
    const fileName = `${scenario.name}.json`;
    
    link.href = URL.createObjectURL(blob);
    link.download = fileName;
    
    document.body.appendChild(link); 
    link.click();
    document.body.removeChild(link); 
    
    URL.revokeObjectURL(link.href);
}
}
