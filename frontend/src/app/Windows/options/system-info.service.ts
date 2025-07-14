import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Subject, Observable, EMPTY, switchMap, catchError, throwError } from 'rxjs';
import { isPlatformBrowser } from '@angular/common';
import { ScenarioService } from '../scenario.service';


@Injectable({ providedIn: 'root' })
export class SystemInfoService {
  private baseUrl = 'http://localhost:8000/system';

  constructor(@Inject(PLATFORM_ID) private platformId: Object, private http: HttpClient, private scenarioService: ScenarioService) {}

  getSystemInfo(): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {  
      return this.scenarioService.handleRequest(this.http.get(`${this.baseUrl}/system-info/`, { headers: this.scenarioService.getAuthHeaders() }));
    }
    return EMPTY;
  }
}
