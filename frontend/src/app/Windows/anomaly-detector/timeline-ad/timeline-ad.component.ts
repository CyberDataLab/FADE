// Angular core and common modules
import { Component, OnInit, Input, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule } from '@angular/common';
import { Chart } from 'chart.js/auto';

// Application-specific imports
import { ScenarioService } from '../../scenario.service';

/**
 * @summary Displays timeline charts and global explanations for anomaly detection metrics.
 * 
 * This component fetches anomaly metrics grouped by execution, visualizes them using Chart.js,
 * and allows the user to explore per-feature anomalies and global SHAP/LIME explanations.
 */
@Component({
  selector: 'app-timeline-ad',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './timeline-ad.component.html',
  styleUrls: ['./timeline-ad.component.css']
})
export class TimelineADComponent implements OnInit {
  /** @summary Scenario UUID from route */
  uuid: string = '';

  /** @summary Anomaly metrics input from parent (optional) */
  @Input() metrics: any[] = [];

  /** @summary Object to store Chart.js instances */
  charts: any = {};

  /** @summary Metrics grouped by execution, model, and feature */
  groupedMetrics: any[] = [];

  /** @summary Flags and data for modal chart/image */
  showModal = false;
  modalChartType = '';
  modalMetric: any = null;
  modalExecutionNumber: number = 0;
  modalFeatureName: string = '';
  modalImageUrl: string | null = null;
  modalImageType: string | null = null;

  /**
   * @summary Injects Angular services for route access, data retrieval, and change detection.
   * 
   * This constructor provides access to the current route parameters, allows
   * interaction with the backend via the ScenarioService, and ensures proper
   * chart rendering by manually triggering change detection when needed.
   * 
   * @param route Provides access to route parameters (e.g. scenario UUID)
   * @param scenarioService Service used to fetch anomaly metrics from the backend
   * @param cdr ChangeDetectorRef used to trigger manual change detection for rendering charts
   */
  constructor(
    private route: ActivatedRoute,
    private scenarioService: ScenarioService,
    private cdr: ChangeDetectorRef 
  ) {}

  /**
   * @summary Initializes the component by loading UUID and fetching metrics.
   */
  ngOnInit(): void {
    this.uuid = this.route.snapshot.paramMap.get('id') || '';
    this.getMetrics();
  }

  /**
   * @summary Creates all charts for each feature of each model.
   */
  private createAllCharts() {
    this.groupedMetrics.forEach(execution => {
      execution.models.forEach((model: any) => {
        model.features.forEach((feature: any) => {
          const chartId = `line-${execution.executionNumber}-${model.safeModelName}-${feature.safeFeatureName}`;
          if (!this.charts[chartId]) {
            this.createLineChart(feature, chartId);
          }
        });
      });
    });
  }

  /**
   * @summary Retrieves anomaly metrics and initializes charts.
   */
  getMetrics(): void {
    this.scenarioService.getScenarioAnomalyMetrics(this.uuid).subscribe({
      next: (data: any) => {
        this.metrics = data.metrics || [];
        this.groupMetricsByExecution();

        // Trigger manual change detection and create charts
        this.cdr.detectChanges();
        this.createAllCharts();
      },
      error: (err: any) => {
        console.error('Error fetching anomaly metrics:', err);
      }
    });
  }

  /**
   * @summary Groups metrics by execution and model/feature hierarchy.
   */
  private groupMetricsByExecution() {
    const executions: any = {};
  
    // Iterate over each metric to organize by execution and model
    this.metrics.forEach(metric => {
      if (!metric.model_name || !metric.execution || !metric.feature_name) return;
  
      // Create safe names for chart element IDs
      const safeModelName = metric.model_name.replace(/[^a-zA-Z0-9]/g, '-');
      const safeFeatureName = metric.feature_name.replace(/[^a-zA-Z0-9]/g, '-');
  
      // Create group for execution if not present
      if (!executions[metric.execution]) {
        executions[metric.execution] = { 
          executionNumber: metric.execution, 
          models: [],
          globalShapImages: metric.global_shap_images || [],
          globalLimeImages: metric.global_lime_images || []
        };
      }
  
      const exec = executions[metric.execution];
  
      // Find or create model within execution
      const model = exec.models.find((m: any) => m.modelName === metric.model_name) || {
        modelName: metric.model_name,
        safeModelName,
        features: []
      };
  
      // Add model to execution if not already included
      if (!exec.models.includes(model)) {
        exec.models.push(model);
      }
  
      // Add feature to model
      model.features.push({
        featureName: metric.feature_name,
        safeFeatureName,
        anomalies: metric.anomalies || { values: [], anomaly_indices: [] }
      });
  
      // Sort features alphabetically
      model.features.sort((a: any, b: any) => 
        a.featureName.localeCompare(b.featureName)
      );
    });
  
    // Only retain the most recent execution for simplicity
    const allExecutions = Object.values(executions) as any[];
    const mostRecent = allExecutions.sort((a, b) => b.executionNumber - a.executionNumber)[0];
  
    this.groupedMetrics = mostRecent ? [mostRecent] : [];
  }

  /**
   * @summary Creates a line chart showing feature values and anomalies.
   * 
   * @param metric Feature object with values and anomaly indices
   * @param chartId Unique identifier for chart canvas
   */
  private createLineChart(metric: any, chartId: string) {
    try {
      const canvas = document.getElementById(chartId);
      if (!canvas) {
        console.error(`Canvas ${chartId} not found`);
        return;
      }

      // Destroy previous chart if exists
      if (this.charts[chartId]) {
        this.charts[chartId].destroy();
      }

      const values = metric.anomalies.values || [];
      const anomalyIndices = new Set(metric.anomalies.anomaly_indices || []);

      // Create Chart.js instance with anomaly highlighting
      this.charts[chartId] = new Chart(canvas as HTMLCanvasElement, {
        type: 'line',
        data: {
          labels: values.map((_: any, i: number) => i.toString()),
          datasets: [{
            label: 'Values',
            data: values,
            borderColor: '#4C86AF',
            tension: 0.1,
            pointRadius: (ctx: any) => anomalyIndices.has(ctx.dataIndex) ? 5 : 0,
            pointBackgroundColor: (ctx: any) => anomalyIndices.has(ctx.dataIndex) ? '#FF5252' : 'transparent',
            pointBorderColor: (ctx: any) => anomalyIndices.has(ctx.dataIndex) ? '#FF5252' : 'transparent'          
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          elements: {
            point: { hitRadius: 10 }
          },
          scales: {
            x: {
              title: { display: true, text: 'Data Point Index' },
              grid: { display: false }
            },
            y: {
              title: { display: true, text: 'Value' },
              beginAtZero: true
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              mode: 'nearest',
              intersect: false,
              callbacks: {
                label: (ctx: any) => {
                  const isAnomaly = anomalyIndices.has(ctx.dataIndex);
                  return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} ${isAnomaly ? ' (Anomaly)' : ''}`;
                }
              }
            }
          }
        }
      });
    } catch (error) {
      console.error(`Error creating line chart ${chartId}:`, error);
    }
  }

  /**
   * @summary Builds a user-friendly title for a global SHAP or LIME image.
   * 
   * @param img The image filename
   * @param type Either 'SHAP' or 'LIME'
   * @returns A readable image title string
   */
  getGlobalTitle(img: string, type: 'SHAP' | 'LIME'): string {
    if (img.includes('normal')) {
      return `Global ${type} for normal data`;
    } else if (img.includes('anomaly')) {
      return `Global ${type} for anomaly data`;
    }
    return `Global ${type}`;
  }
  
  /**
   * @summary Displays a feature-specific chart in a modal view.
   * 
   * @param type The chart type
   * @param executionNumber The execution number
   * @param model The model to which the feature belongs
   * @param feature The feature object to visualize
   */
  showChartInModal(type: string, executionNumber: number, model: any, feature: any) {
    this.showModal = true;
    this.modalChartType = type;
    this.modalExecutionNumber = executionNumber;
    this.modalMetric = model;
    this.modalFeatureName = feature.featureName;

    // Wait for modal render and then draw the chart
    setTimeout(() => {
      const modalCanvasId = 'modal-line-chart';
      const modalCanvas = document.getElementById(modalCanvasId) as HTMLCanvasElement;
      
      if (this.charts[modalCanvasId]) {
        this.charts[modalCanvasId].destroy();
      }

      this.createLineChart(feature, modalCanvasId);
    }, 100);
  }

  /**
   * @summary Displays a global SHAP or LIME image inside a modal view.
   * 
   * @param imageUrl Path to the image
   * @param type Explanation type: SHAP or LIME
   */
  showGlobalImageInModal(imageUrl: string, type: 'SHAP' | 'LIME') {
    this.modalImageUrl = 'http://localhost:8000/media/' + imageUrl;
    this.modalImageType = type;
    this.showModal = true;
  }

  /**
   * @summary Closes the modal view and resets its content.
   */
  closeModal() {
    this.showModal = false;
    this.modalImageUrl = null;
  }

  /**
   * @summary Builds the full image URL for media assets.
   * 
   * @param path Relative path of the image
   * @returns Fully qualified image URL
   */
  getImageUrl(path: string): string {
    return `http://localhost:8000/media/${path}`;
  }
  
}