// Angular core and shared modules
import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common'; 
import { FormsModule } from '@angular/forms'; 
import { RouterModule } from '@angular/router';

// Application-specific models and services
import { UserRegister } from '../../DTOs/UserRegister';
import { AuthenticationService } from '../../Core/services/authentication.service';
import { UserService } from '../../Core/services/user.service';
import { ThemeToggleComponent } from '../../Theme/theme-toggle/theme-toggle.component';

/**
 * @summary Manages user registration via form input.
 * 
 * This component handles user registration logic, validates fields,
 * interacts with backend services, and redirects on success.
 */
@Component({
  selector: 'app-register',
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    ThemeToggleComponent
  ],
  templateUrl: './register.component.html',
  styleUrl: './register.component.css'
})
export class RegisterComponent implements OnInit {

  /** @summary Object bound to registration form fields */
  userRegisterDTO: UserRegister = {
    admin_username: '',
    admin_password: '',
    username: '',
    password: '',
    confirm_password: '',
    first_name: '',
    last_name: '',
    email: ''
  };

  /** @summary Flags for showing validation errors (required fields) */
  admin_usernameError: boolean;
  admin_passwordError: boolean;
  usernameError: boolean;
  passwordError: boolean;
  confirm_passwordError: boolean;
  first_nameError: boolean;
  last_nameError: boolean;
  emailError: boolean;

  /** @summary Flags for invalid input patterns */
  badUsernameError: boolean;
  badPasswordError: boolean;
  badConfirmPasswordError: boolean;
  badEmailError: boolean;

  /** @summary Flags to toggle visibility of password input fields */
  showAdminPassword: boolean;
  showNewPassword: boolean;
  showConfirmPassword: boolean;

  /** @summary Regex patterns used for input validation */
  usernamePattern = /^(?=.*[a-z])(?=.*\d)[A-Za-z\d]{6,}$/;
  passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$/;
  emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/;

  /**
   * @summary Injects authentication and user services, and router.
   * 
   * @param authenticationService Handles user session validation
   * @param userService Registers the new user
   * @param router Handles navigation between views
   */
  constructor(
    private authenticationService: AuthenticationService,
    private userService: UserService,
    private router: Router
  ) {
    this.admin_usernameError = false;
    this.admin_passwordError = false;
    this.usernameError = false;
    this.passwordError = false;
    this.confirm_passwordError = false;
    this.first_nameError = false;
    this.last_nameError = false;
    this.emailError = false;

    this.badUsernameError = false;
    this.badPasswordError = false;
    this.badConfirmPasswordError = false;
    this.badEmailError = false;

    this.showAdminPassword = false;
    this.showNewPassword = false;
    this.showConfirmPassword = false;
  }

  /**
   * @summary Redirects user to dashboard if already authenticated.
   */
  ngOnInit(): void {
    if (this.authenticationService.actualUserValue != null) {
      this.router.navigate(['/dashboard']);
    }
  }

  /**
   * @summary Toggles password visibility in the registration form.
   * 
   * @param field The specific password field to toggle
   */
  toggleVisibility(field: 'admin' | 'new' | 'confirm'): void {
    if (field === 'admin') this.showAdminPassword = !this.showAdminPassword;
    if (field === 'new') this.showNewPassword = !this.showNewPassword;
    if (field === 'confirm') this.showConfirmPassword = !this.showConfirmPassword;
  }

  /**
   * @summary Submits the registration form when Enter key is pressed.
   * 
   * @param event KeyboardEvent triggered by user input
   */
  keyDownFunction(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      this.registerUser();
    }
  }

  /**
   * @summary Validates form fields and performs registration.
   * 
   * If inputs are valid and passwords match, sends registration request
   * and redirects to login view on success. Displays alerts on failure.
   */
  registerUser(): void {
    // Reset all error flags
    this.admin_usernameError = false;
    this.admin_passwordError = false;
    this.usernameError = false;
    this.passwordError = false;
    this.confirm_passwordError = false;
    this.first_nameError = false;
    this.last_nameError = false;
    this.emailError = false;
    this.badUsernameError = false;
    this.badPasswordError = false;
    this.badConfirmPasswordError = false;
    this.badEmailError = false;

    // Validate required fields and patterns
    if (this.userRegisterDTO.admin_username === '') this.admin_usernameError = true;
    if (this.userRegisterDTO.admin_password === '') this.admin_passwordError = true;

    if (this.userRegisterDTO.username === '') this.usernameError = true;
    else if (!this.usernamePattern.test(this.userRegisterDTO.username)) this.badUsernameError = true;

    if (this.userRegisterDTO.password === '') this.passwordError = true;
    else if (!this.passwordPattern.test(this.userRegisterDTO.password)) this.badPasswordError = true;

    if (this.userRegisterDTO.confirm_password === '') this.confirm_passwordError = true;
    else if (!this.passwordPattern.test(this.userRegisterDTO.confirm_password)) this.badConfirmPasswordError = true;

    if (this.userRegisterDTO.first_name === '') this.first_nameError = true;
    if (this.userRegisterDTO.last_name === '') this.last_nameError = true;

    if (this.userRegisterDTO.email === '') this.emailError = true;
    else if (!this.emailPattern.test(this.userRegisterDTO.email)) this.badEmailError = true;

    // Attempt registration if all validations pass
    if (
      this.userRegisterDTO.admin_username !== '' &&
      this.userRegisterDTO.admin_password !== '' &&
      this.userRegisterDTO.username !== '' &&
      this.userRegisterDTO.password !== '' &&
      this.userRegisterDTO.confirm_password !== '' &&
      this.userRegisterDTO.first_name !== '' &&
      this.userRegisterDTO.last_name !== '' &&
      this.userRegisterDTO.email !== '' &&
      !this.badUsernameError &&
      !this.badPasswordError &&
      !this.badConfirmPasswordError &&
      !this.badEmailError
    ) {
      if (this.userRegisterDTO.password !== this.userRegisterDTO.confirm_password) {
        alert("Passwords don't match.");
      } else {
        this.userService.register(this.userRegisterDTO).subscribe(
          () => {
            // Redirect to login on successful registration
            this.router.navigate(['/login']);
          },
          error => {
            // Show backend error message if available
            let errorMessage = 'An unexpected error occurred. Please try again.';
            if (error.error && error.error.error) {
              errorMessage = error.error.error;
            }
            alert(errorMessage);
          }
        );
      }
    }
  }
}
