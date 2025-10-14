// Angular core and common modules
import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { first } from 'rxjs/operators';
import { CommonModule } from '@angular/common'; 
import { FormsModule } from '@angular/forms'; 
import { RouterModule } from '@angular/router';

// Application-specific imports
import { UserLogin } from '../../DTOs/UserLogin';
import { AuthenticationService } from '../../Core/services/authentication.service';
import { ThemeToggleComponent } from '../../Theme/theme-toggle/theme-toggle.component';

/**
 * @summary Manages user authentication via login form.
 * 
 * This component handles user input for logging in, validates fields,
 * calls the authentication service, and redirects users upon success.
 */
@Component({
  selector: 'app-login',
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    ThemeToggleComponent
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent implements OnInit {

  /** @summary Object bound to login form fields */
  userLoginDTO: UserLogin = {
    username: '',
    password: ''
  };

  /** @summary Flags for showing validation errors */
  usernameError: boolean;
  passwordError: boolean;

  /** @summary Flag to toggle password visibility in input field */
  showPassword: boolean;

  /**
   * @summary Injects the authentication service and router.
   * 
   * @param authenticationService Handles login and session tracking
   * @param router Used to navigate between application views
   */
  constructor(
    private authenticationService: AuthenticationService,
    private router: Router
  ) { 
    this.usernameError = false;
    this.passwordError = false;
    this.showPassword = false;
  }

  /**
   * @summary Redirects user to dashboard if already authenticated.
   */
  ngOnInit(): void {
    if (this.authenticationService.actualUserValue != null) {
      this.router.navigate(["/dashboard"]);
    }
  }

  /**
   * @summary Toggles password visibility in the login form.
   */
  togglePasswordVisibility(): void {
    this.showPassword = !this.showPassword;
  }

  /**
   * @summary Submits the login form when Enter key is pressed.
   * 
   * @param event KeyboardEvent triggered by user input
   */
  keyDownFunction(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      this.login();
    }
  }

  /**
   * @summary Validates form fields and performs login.
   * 
   * If credentials are correct, navigates to dashboard. Shows alerts on failure.
   */
  login(): void {
    // Reset error flags
    this.usernameError = false;
    this.passwordError = false;

    // Validate required fields
    if (this.userLoginDTO.username === '') {
      this.usernameError = true;
    }

    if (this.userLoginDTO.password === '') {
      this.passwordError = true;
    }

    // Attempt login if inputs are valid
    if (this.userLoginDTO.username !== '' && this.userLoginDTO.password !== '') {
      this.usernameError = false;
      this.passwordError = false;

      const loginObs = this.authenticationService.login(this.userLoginDTO);

      if (loginObs) {
        loginObs.pipe(first())
          .subscribe(
            data => {
              // Redirect to dashboard on successful login
              this.router.navigate(["/dashboard"]);
            },
            error => {
              // Display login error
              alert('Wrong user or password.');
            }
          );
      } else {
        // Already logged in
        alert('You are already logged in.');
        this.router.navigate(["/dashboard"]);
      }
    } 
  }
}
