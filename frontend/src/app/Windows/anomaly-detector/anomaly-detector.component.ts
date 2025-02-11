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
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    FeaturesComponent,
    TimelineADComponent,
    MetricsComponent
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
      const file = input.files[0];
      const reader = new FileReader();

      reader.onload = (e: ProgressEvent<FileReader>) => {
        try {
          const design = JSON.parse(e.target?.result as string);
          const name = file.name.substring(0, file.name.lastIndexOf('.'));

          this.scenarioService.saveScenario(name, design)
            .subscribe({
              next: () => {
                this.getScenarios();
                alert('Scenario imported correctly.');
              },
              error: () => {
                alert('Unexpected error while importing the scenario.');
              }
            });
        } catch (err) {
          alert('Error loading the scenario. Invalid format.');
        }
      };

      reader.readAsText(file);
    }
    
    input.value = '';
  }

  viewFeatures(scenarioId: number) {
    this.router.navigate(['/features', scenarioId]);
  }
  
  viewTimelineAD(scenarioId: number) {
    this.router.navigate(['/timeline-ad', scenarioId]);
  }
  
  viewMetrics(scenarioId: number) {
    this.router.navigate(['/metrics', scenarioId]);
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

  downloadScenario(scenario: any) {
    const blob = new Blob([JSON.stringify(scenario.design)], { type: 'application/json' });
  
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
