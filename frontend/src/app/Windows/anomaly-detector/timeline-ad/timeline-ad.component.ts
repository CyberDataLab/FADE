import { Component, OnInit, Input, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ScenarioService } from '../../scenario.service';
import { Chart } from 'chart.js/auto';

@Component({
  selector: 'app-timeline-ad',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './timeline-ad.component.html',
  styleUrls: ['./timeline-ad.component.css']
})
export class TimelineADComponent implements OnInit {
  uuid: string = '';
  @Input() metrics: any[] = [];
  charts: any = {};
  groupedMetrics: any[] = [];

  showModal = false;
  modalChartType = '';
  modalMetric: any = null;
  modalExecutionNumber: number = 0;
  modalFeatureName: string = '';

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
        model.features.forEach((feature: any) => {
          const chartId = `line-${execution.executionNumber}-${model.safeModelName}-${feature.safeFeatureName}`;
          if (!this.charts[chartId]) {
            this.createLineChart(feature, chartId);
          }
        });
      });
    });
  }

  getMetrics(): void {
    this.scenarioService.getScenarioAnomalyMetrics(this.uuid).subscribe({
      next: (data: any) => {
        this.metrics = data.metrics || [];
        this.groupMetricsByExecution();
        this.cdr.detectChanges();
        this.createAllCharts();
      },
      error: (err: any) => {
        console.error('Error fetching anomaly metrics:', err);
      }
    });
  }

  private groupMetricsByExecution() {
    const executions: any = {};
    
    this.metrics.forEach(metric => {
      if (!metric.model_name || !metric.execution || !metric.feature_name) {
        console.warn('Invalid metric:', metric);
        return;
      }

      const safeModelName = metric.model_name.replace(/[^a-zA-Z0-9]/g, '-');
      const safeFeatureName = metric.feature_name.replace(/[^a-zA-Z0-9]/g, '-');

      if (!executions[metric.execution]) {
        executions[metric.execution] = { 
          executionNumber: metric.execution, 
          models: [] 
        };
      }

      let model = executions[metric.execution].models.find(
        (m: any) => m.modelName === metric.model_name
      );
      
      if (!model) {
        model = {
          modelName: metric.model_name,
          safeModelName: safeModelName,
          features: []
        };
        executions[metric.execution].models.push(model);
      }

      model.features.push({
        featureName: metric.feature_name,
        safeFeatureName: safeFeatureName,
        anomalies: metric.anomalies || { values: [], anomaly_indices: [] }
      });

      model.features.sort((a: any, b: any) => 
        a.featureName.localeCompare(b.featureName)
      );
    });

    this.groupedMetrics = Object.values(executions);
  }

  private createLineChart(metric: any, chartId: string) {
    try {
      const canvas = document.getElementById(chartId);
      if (!canvas) {
        console.error(`Canvas ${chartId} not found`);
        return;
      }

      if (this.charts[chartId]) {
        this.charts[chartId].destroy();
      }

      const values = metric.anomalies.values || [];
      const anomalyIndices = new Set(metric.anomalies.anomaly_indices || []);

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

  showChartInModal(type: string, executionNumber: number, model: any, feature: any) {
    this.showModal = true;
    this.modalChartType = type;
    this.modalExecutionNumber = executionNumber;
    this.modalMetric = model;
    this.modalFeatureName = feature.featureName;

    setTimeout(() => {
      const modalCanvasId = 'modal-line-chart';
      const modalCanvas = document.getElementById(modalCanvasId) as HTMLCanvasElement;
      
      if (this.charts[modalCanvasId]) {
        this.charts[modalCanvasId].destroy();
      }

      this.createLineChart(feature, modalCanvasId);
    }, 100);
  }

  closeModal() {
    this.showModal = false;
  }
}