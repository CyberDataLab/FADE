// Angular core and common modules
import { Component, OnInit, Inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { PLATFORM_ID } from '@angular/core';
import { FormsModule } from '@angular/forms';

// Application-specific services
import { SystemInfoService } from './system-info.service';

/**
 * @summary Component for managing system configuration options.
 * 
 * This component loads and displays system information and configurable
 * fields like the interface, username, and path to `tshark`. It allows 
 * users to edit and save these configurations.
 */
@Component({
    selector: 'app-options',
    imports: [
        CommonModule,
        FormsModule
      ],
    templateUrl: './options.component.html',
    styleUrl: './options.component.css'
})
export class OptionsComponent implements OnInit {

  /** @summary System information object loaded from the backend */
  system: any = null;

  /** @summary User-editable system configuration fields */
  userInputs = {
    host_username: '',
    tshark_path: '',
    interface: ''
  };

  /**
   * @summary Injects platform context and system service.
   * 
   * @param platformId Used to check if code is running in the browser
   * @param systemService Handles loading and saving system configuration
   */
  constructor(
    @Inject(PLATFORM_ID) private platformId: Object, 
    private systemService: SystemInfoService
  ) {}

  /**
   * @summary Loads system info and configuration on initialization.
   */
  ngOnInit(): void {
    // Ensure this code runs only in browser context
    if (isPlatformBrowser(this.platformId)) {
      // Load system metadata (CPU, GPU, etc.)
      this.systemService.getSystemInfo().subscribe((data: any) => {
        this.system = data;
      });
  
      // Load saved configuration values, if any
      this.systemService.getSystemConfig().subscribe((config: any) => {
        this.userInputs.host_username = config.host_username || '';
        this.userInputs.tshark_path = config.tshark_path || '';
        this.userInputs.interface = config.interface || '';
      });
    }
  }

  /**
   * @summary Sends updated configuration values to the backend.
   */
  saveInputs(): void {
    const payload = {
      host_username: this.userInputs.host_username,
      tshark_path: this.userInputs.tshark_path,
      interface: this.userInputs.interface
    };
  
    // Save settings via the service and notify user
    this.systemService.saveSystemConfig(payload).subscribe({
      next: () => alert('Configuration saved successfully'),
      error: err => console.error('Failed to save config:', err)
    });
  }
}