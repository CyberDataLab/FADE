// Angular core and common modules
import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, EMPTY } from 'rxjs';
import { isPlatformBrowser } from '@angular/common';

// Application-specific service
import { ScenarioService } from './scenario.service';

/**
 * @summary Service for retrieving and updating system-related information.
 * 
 * This service allows the frontend to fetch host details (CPU, RAM, etc.)
 * and save or retrieve configuration settings, such as capture interface or `tshark` path.
 */
@Injectable({
  providedIn: 'root'
})
export class SystemInfoService {

  /** @summary Base API URL for system-related endpoints */
  private baseUrl = 'http://localhost:8000/system';

  /**
   * @summary Initializes platform context and dependencies.
   * 
   * @param platformId Platform token to detect browser/server context
   * @param http Angular HttpClient to perform HTTP requests
   * @param scenarioService Wrapper service for handling authenticated requests
   */
  constructor(
    @Inject(PLATFORM_ID) private platformId: Object,
    private http: HttpClient,
    private scenarioService: ScenarioService
  ) {}

  /**
   * @summary Fetches system information such as CPU, GPU, RAM, hostname, etc.
   * 
   * @returns Observable with system information, or `EMPTY` if not in browser
   */
  getSystemInfo(): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {  
      return this.scenarioService.handleRequest(this.http.get(`${this.baseUrl}/system-info/`, { headers: this.scenarioService.getAuthHeaders() }));
    }
    return EMPTY;
  }

  /**
   * @summary Saves user-defined system configuration (e.g., capture interface, tshark path).
   * 
   * @param data Object containing configuration fields to be persisted
   * @returns Observable with the result of the operation, or `EMPTY` if not in browser
   */
  saveSystemConfig(data: any): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {  
      return this.scenarioService.handleRequest(this.http.post(`${this.baseUrl}/system-config/`, data, 
        { headers: this.scenarioService.getAuthHeaders() }));
    }
    return EMPTY;
  }

  /**
   * @summary Retrieves previously saved system configuration from the backend.
   * 
   * @returns Observable with system configuration, or `EMPTY` if not in browser
   */
  getSystemConfig(): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.scenarioService.handleRequest(this.http.get(`${this.baseUrl}/system-config/`, {
          headers: this.scenarioService.getAuthHeaders()
        })
      );
    }
    return EMPTY;
  }
}
