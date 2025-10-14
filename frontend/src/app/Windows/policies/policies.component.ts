// Angular core and common modules
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common'; 
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

// Application-specific service and interface
import { PoliciesService, PolicyPayload } from '../../Core/services/policies.service';


/**
 * @summary Component for configuring and applying security policies.
 * 
 * This component allows the user to select a policy type (e.g., block IP, send email),
 * enter the target and reason, and apply it via the backend using `PoliciesService`.
 */
@Component({
    selector: 'app-policies',
    imports: [
      CommonModule,
      FormsModule],
    templateUrl: './policies.component.html',
    styleUrl: './policies.component.css'
})

export class PoliciesComponent {
  /** @summary Selected policy type from the dropdown (e.g., block_ip, send_email) */
  policyType: string = '';

  /** @summary Target value associated with the policy (e.g., IP, port, interface) */
  targetValue: string = '';

  /** @summary Internally selected reason for triggering the policy */
  private _selectedReason: string = '';

  /** @summary Value tied to the selected reason (e.g., threshold) */
  reasonValue: string | number = '';

  /** @summary Message returned from backend after applying policy */
  resultMessage: string = '';

  /** @summary Field monitored when using "send_email" policies (e.g., IP, port) */
  monitorTarget: string = '';

  /** @summary Threshold value used for triggering monitoring-based policies */
  monitorThreshold: number | null = null;

  /** @summary Predefined list of policy reasons shown in dropdown */
  predefinedReasons: string[] = [
    'Excessive number of packets from a specific IP',
    'Excessive number of packets from a specific port',
    'High bandwidth usage in a short time',
  ];

   // sin selección inicial para que se vea el placeholder
  policyTypes = [
    { value: 'block_ip_src',  label: 'Block src IP' },
    { value: 'block_ip_dst',  label: 'Block dst IP' },
    { value: 'allow_ip_src',  label: 'Allow src IP' },
    { value: 'allow_ip_dst',  label: 'Allow dst IP' },
    { value: 'block_port_src',label: 'Block src port' },
    { value: 'block_port_dst',label: 'Block dst port' },
    { value: 'allow_port_src',label: 'Allow src port' },
    { value: 'allow_port_dst',label: 'Allow dst port' },
    { value: 'limit_bandwidth',label: 'Limit Bandwidth' },
    { value: 'send_email',    label: 'Send Email' },
  ];

  // Mapa de placeholders por tipo de policy
  private placeholders: Record<string, string> = {
    block_ip_src:   'e.g., 192.168.1.10',
    block_ip_dst:   'e.g., 192.168.1.20',
    allow_ip_src:   'e.g., 10.0.0.5',
    allow_ip_dst:   'e.g., 10.0.0.8',
    block_port_src: 'e.g., 22',
    block_port_dst: 'e.g., 443',
    allow_port_src: 'e.g., 8080',
    allow_port_dst: 'e.g., 8443',
    limit_bandwidth:'e.g., 10mbps',
    send_email:     'Choose reason / configure below',
  };

  /**
   * @summary Injects HTTP client and policies service.
   * 
   * @param http Angular HttpClient for manual calls (optional)
   * @param policiesService Service that applies policy to backend
   */
  constructor(
    private http: HttpClient,
    private policiesService: PoliciesService
  ) {}

  /**
   * @summary Getter for selected reason (used in two-way binding).
   * 
   * @returns The currently selected reason string
   */
  get selectedReason(): string {
    return this._selectedReason;
  }

  /**
   * @summary Setter for selected reason. Resets reason value when changed.
   * 
   * @param reason Reason selected from predefined list
   */
  set selectedReason(reason: string) {
    this._selectedReason = reason;
    this.reasonValue = '';
  }

  /**
   * @summary Returns a placeholder text depending on selected policy type.
   * 
   * @returns Placeholder string for the main input field
   */
  getPlaceholderFor(type?: string | null): string {
    return type && this.placeholders[type] ? this.placeholders[type] : 'Select a policy to see hint';
  }

  /**
   * @summary Returns a placeholder string depending on the selected reason.
   * 
   * @returns Placeholder string for the reason-related input field
   */
  getReasonPlaceholder(): string {
    if (!this.selectedReason) return '';
    if (this.selectedReason.includes('IP')) return 'e.g., 192.168.1.1';
    if (this.selectedReason.includes('port') || this.selectedReason.includes('Port')) return 'e.g., 443';
    if (this.selectedReason.includes('short time')) return 'e.g., 60 (seconds)';
    return '';
  }

  /**
   * @summary Determines whether the reason input expects a numeric value.
   * 
   * @returns `true` if reason is time-based and requires numeric input; otherwise `false`
   */
  isReasonNumeric(): boolean {
    return this.selectedReason.includes('short time');
  }

  /**
   * @summary Builds a policy payload and sends it to the backend.
   * 
   * The payload structure varies based on the selected policy type.
   * Handles success and error responses from the `PoliciesService`.
   * 
   * @returns void
   */
  applyPolicy() {
    const payload: PolicyPayload = {
      type: this.policyType,
      ...(this.targetValue && { value: this.targetValue }),
      reason: this.selectedReason,
      ...(this.policyType === 'send_email' && {
        monitorTarget: this.monitorTarget,
        monitorThreshold: this.monitorThreshold
      })
    };
  
    this.policiesService.applyPolicy(payload).subscribe({
      next: (res) => (this.resultMessage = res.message),
      error: (err) => (this.resultMessage = err.error?.message || 'Error applying policy')
    });
  }
}