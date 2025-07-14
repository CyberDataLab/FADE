import { Component, OnInit, Inject } from '@angular/core';
import { SystemInfoService } from './system-info.service';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { PLATFORM_ID } from '@angular/core';


@Component({
    selector: 'app-options',
    imports: [
        CommonModule
      ],
    templateUrl: './options.component.html',
    styleUrl: './options.component.css'
})
export class OptionsComponent implements OnInit {
    system: any = null;
  
    constructor(@Inject(PLATFORM_ID) private platformId: Object, private systemService: SystemInfoService) {}
  
    ngOnInit(): void {
      if (isPlatformBrowser(this.platformId)) {
        this.systemService.getSystemInfo().subscribe((data:any) => {
          this.system = data;
        });
      }
    }
  }
