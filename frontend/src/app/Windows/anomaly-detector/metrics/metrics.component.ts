import { Component, OnInit, Input, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ScenarioService } from '../../scenario.service';
import { Chart } from 'chart.js/auto';

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

  constructor(
    private route: ActivatedRoute,
    private scenarioService: ScenarioService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.uuid = this.route.snapshot.paramMap.get('id') || '';
    this.getMetrics();
  }

  private createAllCharts() {
    this.groupedMetrics.forEach(execution => {
      execution.models.forEach((model: any) => {
        const barChartId = `bar-${execution.executionNumber}-${model.safeModelName}`;
        const matrixChartId = `matrix-${execution.executionNumber}-${model.safeModelName}`;
        
        if (!this.charts[barChartId]) {
          this.createBarChart(model, barChartId);
        }
        if (!this.charts[matrixChartId]) {
          this.createConfusionMatrix(model, matrixChartId);
        }
      });
    });
  }

  getMetrics(): void {
    this.scenarioService.getScenarioClassificationMetrics(this.uuid).subscribe({
      next: (data: any) => {
        this.metrics = data.metrics || [];
        this.groupMetricsByExecution();
        
        this.cdr.detectChanges();
        this.createAllCharts();
      },
      error: (err: any) => {
        console.error('Error fetching metrics:', err);
      }
    });
  }

  private groupMetricsByExecution() {
    const executions: any = {};
    
    this.metrics.forEach(metric => {
      if (!metric.model_name || !metric.execution) {
        console.warn('Invalid metric:', metric);
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
        accuracy: metric.accuracy || 0,
        precision: metric.precision || 0,
        recall: metric.recall || 0,
        f1_score: metric.f1_score || 0,
        confusion_matrix: metric.confusion_matrix || []
      });
    });
  
    this.groupedMetrics = Object.values(executions);
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
      // Esperamos un pequeño momento antes de crear el gráfico
      const modalCanvasId = `modal-${type}-chart`;
      
      // Limpiamos el gráfico previo si existe
      const modalCanvas = document.getElementById(modalCanvasId) as HTMLCanvasElement;
      if (modalCanvas && this.charts[modalCanvasId]) {
        this.charts[modalCanvasId].destroy();
      }
  
      if (type === 'bar') {
        this.createBarChart(this.modalMetric, modalCanvasId);
      } else if (type === 'matrix') {
        this.createConfusionMatrix(this.modalMetric, modalCanvasId);
      }
    }, 100); // Le damos un pequeño delay para asegurarnos que el modal se haya renderizado
  }
  

  closeModal() {
    this.showModal = false;
  }
}
