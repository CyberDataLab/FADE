// Angular core and common modules
import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, EMPTY } from 'rxjs';
import { isPlatformBrowser } from '@angular/common';

// Application-specific services
import { ScenarioService } from '../scenario.service';

/**
 * @summary Interface for defining a policy payload structure.
 */
export interface PolicyPayload {
  /** @summary Type of the policy (e.g., 'send_email', 'block_ip_src', etc.) */
  type: string;

  /** @summary Optional value associated with the policy (e.g., IP or email) */
  value?: string;

  /** @summary Optional reason for triggering the policy */
  reason?: string;

  /** @summary Target field to monitor (e.g., 'ip', 'port') */
  monitorTarget?: string;

  /** @summary Threshold value to trigger the policy */
  monitorThreshold?: number | null;
}

/**
 * @summary Service for applying anomaly response policies.
 * 
 * This service communicates with the backend API to apply predefined
 * security or monitoring actions based on the scenario logic.
 */
@Injectable({
  providedIn: 'root'
})
export class PoliciesService {

  /** @summary Backend API endpoint for applying a policy */
  private apiUrl = 'http://localhost:8000/action/apply-policy/';

  /**
   * @summary Injects HTTP client, platform check, and scenario context.
   * 
   * @param platformId Angular token to detect browser vs server context
   * @param http Angular HttpClient for API communication
   * @param scenarioService Provides authentication headers and request wrappers
   */
  constructor(
    @Inject(PLATFORM_ID) private platformId: Object,
    private http: HttpClient,
    private scenarioService: ScenarioService
  ) {}

  /**
   * @summary Sends a policy to the backend if running in the browser.
   * 
   * @param payload Object representing the policy to apply
   * @returns Observable of the HTTP response, or EMPTY if not in browser
   */
  applyPolicy(payload: PolicyPayload): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {  
      return this.scenarioService.handleRequest(this.http.post(this.apiUrl, payload, 
        { headers: this.scenarioService.getAuthHeaders() }));
    }
    return EMPTY;
  }
}
