import { Component, OnInit, Input, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ScenarioService } from '../../scenario.service';
import { Chart } from 'chart.js/auto';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-metrics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './metrics.component.html',
  styleUrls: ['./metrics.component.css']
})
export class MetricsComponent implements OnInit {
  uuid: string = '';
  @Input() metrics: any[] = [];
  charts: any = {};
  groupedMetrics: any[] = [];

  showModal = false;
  modalChartType = '';
  modalMetric: any = null;
  modalExecutionNumber: number = 0;
  modalImageUrl: string | null = null;
  modalImageLabel: string | null = null;  

  private modelTypes: {
    classification: string[],
    regression: string[]
  } = { classification: [], regression: [] };

  constructor(
    private route: ActivatedRoute,
    private scenarioService: ScenarioService,
    private cdr: ChangeDetectorRef,
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    this.uuid = this.route.snapshot.paramMap.get('id') || '';
    this.loadConfig();
    this.getMetrics();
  }

  private loadConfig(): void {
    this.http.get('assets/config.json').subscribe({
      next: (config: any) => {
        this.modelTypes.classification = config.sections.dataModel.classification.map((m: any) => m.type);
        this.modelTypes.regression = config.sections.dataModel.regression.map((m: any) => m.type);
      },
      error: (err:any) => console.error('Error loading config:', err)
    });
  }

  private createAllCharts() {
    this.groupedMetrics.forEach(execution => {
      execution.models.forEach((model: any) => {
        if (model.modelType === 'classification') {
          const barChartId = `bar-${execution.executionNumber}-${model.safeModelName}`;
          const matrixChartId = `matrix-${execution.executionNumber}-${model.safeModelName}`;
          
          if (!this.charts[barChartId]) this.createBarChart(model, barChartId);
          if (!this.charts[matrixChartId]) this.createConfusionMatrix(model, matrixChartId);
        } else if (model.modelType === 'regression') {
          const regressionChartId = `regression-${execution.executionNumber}-${model.safeModelName}`;
          if (!this.charts[regressionChartId]) this.createRegressionChart(model, regressionChartId);
        }
      });
    });
  }

  getMetrics(): void {
    this.scenarioService.getScenarioClassificationMetrics(this.uuid).subscribe({
      next: (classificationData: any) => {
        this.metrics = classificationData.metrics || [];
        
        this.scenarioService.getScenarioRegressionMetrics(this.uuid).subscribe({
          next: (regressionData: any) => {
            this.metrics = [...this.metrics, ...(regressionData.metrics || [])];
            this.groupMetricsByExecution();
            this.cdr.detectChanges();
            this.createAllCharts();
          },
          error: (err: any) => console.error('Error fetching regression metrics:', err)
        });
      },
      error: (err: any) => console.error('Error fetching classification metrics:', err)
    });
  }

  private groupMetricsByExecution() {
    const executions: any = {};
    
    this.metrics.forEach(metric => {
      if (!metric.model_name || !metric.execution) return;
  
      const isClassification = this.modelTypes.classification.includes(metric.model_name);
      const isRegression = this.modelTypes.regression.includes(metric.model_name);

      if (!isClassification && !isRegression) {
        return;
      }
      
      const safeModelName = metric.model_name.replace(/[^a-zA-Z0-9]/g, '-');
  
      if (!executions[metric.execution]) {
        executions[metric.execution] = { 
          executionNumber: metric.execution, 
          models: [] 
        };
      }
      
      executions[metric.execution].models.push({
        modelName: metric.model_name,
        safeModelName: safeModelName,
        modelType: isClassification ? 'classification' : 'regression',
        accuracy: metric.accuracy,
        precision: metric.precision,
        recall: metric.recall,
        f1_score: metric.f1_score,
        confusion_matrix: metric.confusion_matrix,
        mse: metric.mse,
        rmse: metric.rmse,
        mae: metric.mae,
        r2: metric.r2,
        msle: metric.msle,
        global_shap_images: metric.global_shap_images || [],
        global_lime_images: metric.global_lime_images || []
      });
    });
  
    this.groupedMetrics = [Object.values(executions).sort((a: any, b: any) => b.executionNumber - a.executionNumber)[0]];

  }

  private createRegressionChart(metric: any, chartId: string) {
    try {
      const canvas = document.getElementById(chartId);
      if (!canvas) return;
  
      if (this.charts[chartId]) {
        this.charts[chartId].destroy();
      }
  
      this.charts[chartId] = new Chart(canvas as HTMLCanvasElement, {
        type: 'bar',
        data: {
          labels: ['MSE', 'RMSE', 'MAE', 'R²', 'MSLE'],
          datasets: [{
            label: 'Regression Metrics',
            data: [
              metric.mse,
              metric.rmse,
              metric.mae,
              metric.r2,
              metric.msle
            ],
            backgroundColor: 'rgba(255, 159, 64, 0.8)',
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true }
          }
        }
      });
    } catch (error) {
      console.error(`Error creating regression chart ${chartId}:`, error);
    }
  }

  private createBarChart(metric: any, chartId: string) {
    try {
      const safeMetric = {
        accuracy: Number(metric.accuracy || 0),
        precision: Number(metric.precision || 0),
        recall: Number(metric.recall || 0),
        f1_score: Number(metric.f1_score || 0)
      };

      const canvas = document.getElementById(chartId);
      if (!canvas) {
        console.error(`Canvas ${chartId} not found`);
        return;
      }

      if (this.charts[chartId]) {
        this.charts[chartId].destroy();
      }

      this.charts[chartId] = new Chart(canvas as HTMLCanvasElement, {
        type: 'bar',
        data: {
          labels: ['Accuracy', 'Precision', 'Recall', 'F1 Score'],
          datasets: [{
            label: 'Metrics',
            data: [
              safeMetric.accuracy,
              safeMetric.precision,
              safeMetric.recall,
              safeMetric.f1_score
            ],
            backgroundColor: [
              'rgba(54, 162, 235, 0.8)',
              'rgba(75, 192, 192, 0.8)',
              'rgba(255, 99, 132, 0.8)',
              'rgba(153, 102, 255, 0.8)'
            ],
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
                beginAtZero: true,
                max: 1
            }
          }
        }
      });
    } catch (error) {
        console.error(`Error creating bar chart ${chartId}:`, error);
    }
  }

  private createConfusionMatrix(metric: any, chartId: string) {
    try {
      const canvas = document.getElementById(chartId) as HTMLCanvasElement;
      if (!canvas) {
        console.error(`Canvas element #${chartId} not found.`);
        return;
      }

      if (!metric.confusion_matrix) {
        console.warn(`No confusion matrix data for ${chartId}`);
        return;
      }

      let confusionMatrix = metric.confusion_matrix;
      if (typeof confusionMatrix === 'string') {
        confusionMatrix = JSON.parse(confusionMatrix);
      }

      if (this.charts[chartId]) {
        this.charts[chartId].destroy();
      }

      const labels = confusionMatrix.map((_: any, i: number) => `Class ${i + 1}`);
      const dataPoints = confusionMatrix.flatMap((row: number[], y: number) =>
        row.map((value: number, x: number) => ({ x, y, v: value }))
      );
      const maxValue = Math.max(...confusionMatrix.flat());

      this.charts[chartId] = new Chart(canvas, {
        type: 'scatter',
        data: {
          datasets: [{
            label: 'Confusion Matrix',
            data: dataPoints,
            backgroundColor: (ctx: any) => `rgba(63, 81, 181, ${ctx.raw.v / maxValue})`,
            pointRadius: 15,
            pointStyle: 'rect'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              type: 'linear',
              offset: true,
              min: -0.5,
              max: confusionMatrix[0].length - 0.5,
              ticks: {
                stepSize: 1,
                callback: (value: any) => labels[value]
              },
              title: { display: true, text: 'Predicted' }
            },
            y: {
              type: 'linear',
              reverse: true,
              min: -0.5,
              max: confusionMatrix.length - 0.5,
              ticks: {
                stepSize: 1,
                callback: (value: any) => labels[value]
              },
              title: { display: true, text: 'Actual' }
            }
          },
          plugins: {
            tooltip: {
              callbacks: {
                label: (ctx: any) => {
                  return `Actual: ${labels[ctx.parsed.y]}\nPredicted: ${labels[ctx.parsed.x]}\nCount: ${ctx.raw.v}`;
                }
              }
            }
          }
        }
      });
    } catch (error) {
      console.error(`Error creating confusion matrix ${chartId}:`, error);
    }
  }

  showChartInModal(type: string, executionNumber: number, model: any) {
    this.showModal = true;
    this.modalChartType = type;
    this.modalExecutionNumber = executionNumber;
    this.modalMetric = model;
  
    setTimeout(() => {
      const modalCanvasId = `modal-${type}-chart`;
      const modalCanvas = document.getElementById(modalCanvasId) as HTMLCanvasElement;
      
      if (modalCanvas && this.charts[modalCanvasId]) {
        this.charts[modalCanvasId].destroy();
      }
  
      if (type === 'bar') {
        this.createBarChart(this.modalMetric, modalCanvasId);
      } else if (type === 'matrix') {
        this.createConfusionMatrix(this.modalMetric, modalCanvasId);
      } else if (type === 'regression') {
        this.createRegressionChart(this.modalMetric, modalCanvasId);
      }
    }, 100);
  }

  openModal(imageUrl: string) {
  this.modalImageUrl = imageUrl;
  this.modalImageLabel = this.extractClassLabel(imageUrl);
  this.showModal = true;
}

extractClassLabel(filePath: string): string {
  const filename = filePath.split('/').pop() || '';
  const parts = filename.replace('.png', '').split('_');
  return parts[parts.length - 1] || 'unknown';
}


closeModal() {
  this.showModal = false;
  this.modalImageUrl = null;
  this.modalImageLabel = null;
}
}
