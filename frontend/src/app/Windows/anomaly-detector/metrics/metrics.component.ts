import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ScenarioService } from '../../scenario.service';

@Component({
  selector: 'app-metrics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './metrics.component.html',
  styleUrl: './metrics.component.css'
})
export class MetricsComponent {
  uuid: string = '';
  metrics: any[] = [];

  constructor(private route: ActivatedRoute, private scenarioService: ScenarioService) {}

  ngOnInit(): void {
    this.uuid = this.route.snapshot.paramMap.get('id') || '';
    this.getMetrics();
  }

  getMetrics(): void {
    this.scenarioService.getScenarioMetrics(this.uuid).subscribe({
      next: (data: any) => {
        this.metrics = data.metrics || []; // Asegurar que siempre sea un array
        console.log('Métricas recibidas:', this.metrics);
      },
      error: (err: any) => {
        console.error('Error fetching metrics:', err);
      }
    });
  }
}
