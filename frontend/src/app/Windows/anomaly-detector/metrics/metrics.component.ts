import { Component, OnInit, Input, AfterViewChecked } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ScenarioService } from '../../scenario.service';
import { Chart } from 'chart.js/auto';

@Component({
    selector: 'app-metrics',
    imports: [CommonModule],
    templateUrl: './metrics.component.html',
    styleUrl: './metrics.component.css'
})
export class MetricsComponent implements OnInit, AfterViewChecked {
  uuid: string = '';
  @Input() metrics: any[] = [];
  chart: any;

  constructor(private route: ActivatedRoute, private scenarioService: ScenarioService) {}

  ngOnInit(): void {
    this.uuid = this.route.snapshot.paramMap.get('id') || '';
    this.getMetrics();
  }

  ngAfterViewChecked() {
    if (this.metrics.length > 0 && !this.chart) {
      this.createChart();
      this.createConfusionMatrixHeatmap();
    }
  }

  getMetrics(): void {
    this.scenarioService.getScenarioMetrics(this.uuid).subscribe({
      next: (data: any) => {
        this.metrics = data.metrics || []; 
        console.log('Métricas recibidas:', this.metrics);
      },
      error: (err: any) => {
        console.error('Error fetching metrics:', err);
      }
    });
  }

  createChart() {
    const ctx = document.getElementById('metricsChart') as HTMLCanvasElement;
  
    const data = {
      labels: ['Accuracy', 'Precision', 'Recall', 'F1 Score'],
      datasets: [{
        data: [
          this.metrics[0].accuracy,
          this.metrics[0].precision,
          this.metrics[0].recall,
          this.metrics[0].f1_score
        ],
        backgroundColor: [
          'rgba(54, 162, 235, 0.8)',  
          'rgba(75, 192, 192, 0.8)',  
          'rgba(255, 99, 132, 0.8)',  
          'rgba(153, 102, 255, 0.8)'  
        ],
        borderColor: [
          'rgba(54, 162, 235, 1)', 
          'rgba(75, 192, 192, 1)',
          'rgba(255, 99, 132, 1)',
          'rgba(153, 102, 255, 1)'
        ],
        borderWidth: 2 
      }]
    };
  
    this.chart = new Chart(ctx, {
      type: 'bar',
      data: data,
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: `Metrics of the model: ${this.metrics[0].model_name}`,
            font: {
              size: 24,
              family: 'Arial',
              weight: 'bold'
            },
            color: '#000',
            padding: {
              top: 20,
              bottom: 20
            }
          },
          legend: {
            display: false 
          }
        },
        scales: {
          y: {
            min: 0,
            ticks: {
              color: '#000',
              font: {
                size: 18
              }
            }
          },
          x: {
            ticks: {
              color: '#000',
              font: {
                size: 18
              }
            }
          }
        }
      }
    });
  }
  
  createConfusionMatrixHeatmap() {
    const ctx = document.getElementById('confusionMatrixChart') as HTMLCanvasElement;
    const confusionMatrix = this.metrics[0].confusion_matrix;
  
    const data = {
      labels: Array.from({ length: confusionMatrix.length }, (_, i) => `Clase ${i}`),
      datasets: confusionMatrix.map((row: number[], rowIndex: number) => ({
        label: `Clase ${rowIndex}`,
        data: row.map((value: number, colIndex: number) => ({
          x: colIndex,
          y: rowIndex,
          v: value
        })),
        backgroundColor: row.map(value => `rgba(0, 123, 255, ${value / Math.max(...row)})`),
        borderColor: 'black',
        borderWidth: 1
      }))
    };
  
    this.chart = new Chart(ctx, {
      type: 'scatter',
      data: data,
      options: {
        responsive: true,
        plugins: {
          title: { 
            display: true,
            text: 'Matriz de Confusión'
          }
        },
        scales: {
          x: {
            type: 'linear',
            position: 'bottom',
            min: 0,
            max: confusionMatrix[0].length - 1,
            ticks: {
              stepSize: 1
            }
          },
          y: {
            type: 'linear',
            min: 0,
            max: confusionMatrix.length - 1,
            ticks: {
              stepSize: 1
            }
          }
        }
      }
    });
  }
  
  

  
}