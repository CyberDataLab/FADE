import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { AnomalyDetectorComponent } from '../anomaly-detector/anomaly-detector.component';
import { XaiComponent } from '../xai/xai.component';
import { PoliciesComponent } from '../policies/policies.component';
import { OptionsComponent } from '../options/options.component';
import { UserComponent } from '../user/user.component'
import { AuthenticationService } from '../../Authentication/authentication.service';
import { Location } from '@angular/common';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule,
    RouterModule,
    AnomalyDetectorComponent,
    XaiComponent,
    PoliciesComponent,
    OptionsComponent,
    UserComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent {

  constructor(private authenticationService: AuthenticationService, private router: Router, private location: Location) { }

  navigateTo(path: string): void {
    this.router.navigate([`/dashboard/${path}`]);
  }

  isDashboard(): boolean {
    return this.router.url === '/dashboard';
  }

  goBack(): void {
    const currentUrl = this.router.url;
    const urlParts = currentUrl.split('/');

    if (urlParts.length > 3) {
      urlParts.pop(); 
      const newUrl = urlParts.join('/'); 
      this.router.navigateByUrl(newUrl); 
    } else {
      this.router.navigate(['/dashboard']);
    }
  }

  logout(){
    if(this.authenticationService.logout()){
      alert("Logout correctly.");
      this.router.navigate(["/login"])
    }
  }

}