import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { AnomalyDetectorComponent } from '../anomaly-detector/anomaly-detector.component';
import { XaiComponent } from '../xai/xai.component';
import { PoliciesComponent } from '../policies/policies.component';
import { OptionsComponent } from '../options/options.component';
import { UserComponent } from '../user/user.component'
import { AuthenticationService } from '../../Authentication/authentication.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule,
    AnomalyDetectorComponent,
    XaiComponent,
    PoliciesComponent,
    OptionsComponent,
    UserComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent {
  selectedOption: number | null = null; 

  constructor(private authenticationService: AuthenticationService, private router: Router) { }

  selectOption(option: number | null) {
    this.selectedOption = option;
  }

  logout(){
    if(this.authenticationService.logout()){
      alert("Logout correctly.");
      this.router.navigate(["/login"])
    }
  }

}