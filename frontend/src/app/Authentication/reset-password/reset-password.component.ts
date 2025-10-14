// Angular core and shared modules
import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, Params } from '@angular/router';
import { CommonModule } from '@angular/common'; 
import { FormsModule } from '@angular/forms'; 
import { RouterModule } from '@angular/router';

// Application-specific models and services
import { UserPatch } from '../../DTOs/UserPatch';
import { UserService } from '../../Core/services/user.service';
import { ThemeToggleComponent } from '../../Theme/theme-toggle/theme-toggle.component';

/**
 * @summary Manages the password reset functionality.
 * 
 * This component validates new passwords, extracts the reset token from URL,
 * and calls the backend service to update the user's password.
 */
@Component({
  selector: 'app-reset-password',
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    ThemeToggleComponent
  ],
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.css'
})
export class ResetPasswordComponent implements OnInit {

  /** @summary Object bound to the reset form fields */
  userPatchDTO: UserPatch = {
    username: '',
    old_password: '',
    new_password: '',
    confirm_new_password: '',
    email: ''
  };

  /** @summary Flag to toggle visibility of new password input */
  showPassword: boolean;

  /** @summary Flag to toggle visibility of confirm password input */
  showConfirmPassword: boolean;

  /** @summary Reset token extracted from the query parameters */
  token: string;

  /** @summary Flags for required field validation */
  new_passwordError: boolean;
  confirm_new_passwordError: boolean;

  /** @summary Flags for invalid pattern validation */
  badNew_passwordError: boolean;
  badConfirm_new_passwordError: boolean;

  /** @summary Regex pattern for validating new passwords */
  passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$/;

  /**
   * @summary Injects required services.
   * 
   * @param route Extracts token from query parameters
   * @param userService Handles password reset request
   * @param router Navigates between views
   */
  constructor(
    private route: ActivatedRoute,
    private userService: UserService,
    private router: Router
  ) {
    this.new_passwordError = false;
    this.confirm_new_passwordError = false;
    this.badNew_passwordError = false;
    this.badConfirm_new_passwordError = false;
    this.token = '';
    this.showPassword = false;
    this.showConfirmPassword = false;
  }

  /**
   * @summary Retrieves token from URL query params on component init.
   */
  ngOnInit(): void {
    this.route.queryParams.subscribe((params: Params) => {
      this.token = params['token'];
    });
  }

  /**
   * @summary Submits the reset form when Enter key is pressed.
   * 
   * @param event KeyboardEvent triggered by user input
   */
  keyDownFunction(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      this.resetPassword();
    }
  }

  /**
   * @summary Toggles visibility of the new password input field.
   */
  togglePasswordVisibility(): void {
    this.showPassword = !this.showPassword;
  }

  /**
   * @summary Toggles visibility of the confirm password input field.
   */
  toggleConfirmPasswordVisibility(): void {
    this.showConfirmPassword = !this.showConfirmPassword;
  }

  /**
   * @summary Validates inputs and sends reset password request.
   * 
   * If validation passes and passwords match, calls backend to update password.
   * Redirects to login on success, or shows error message on failure.
   */
  resetPassword(): void {
    // Reset all validation flags
    this.new_passwordError = false;
    this.confirm_new_passwordError = false;
    this.badNew_passwordError = false;
    this.badConfirm_new_passwordError = false;

    // Validate required fields and format
    if (this.userPatchDTO.new_password === '') {
      this.new_passwordError = true;
    } else if (!this.passwordPattern.test(this.userPatchDTO.new_password)) {
      this.badNew_passwordError = true;
    }

    if (this.userPatchDTO.confirm_new_password === '') {
      this.confirm_new_passwordError = true;
    } else if (!this.passwordPattern.test(this.userPatchDTO.confirm_new_password)) {
      this.badConfirm_new_passwordError = true;
    }

    // Submit if validations pass
    if (
      this.userPatchDTO.new_password !== '' &&
      this.userPatchDTO.confirm_new_password !== '' &&
      !this.badNew_passwordError &&
      !this.badConfirm_new_passwordError
    ) {
      if (this.userPatchDTO.new_password !== this.userPatchDTO.confirm_new_password) {
        alert("Passwords don't match.");
      } else {
        this.userService.reset_password(this.userPatchDTO.new_password, this.token).subscribe(
          () => {
            this.router.navigate(['/login']);
          },
          (error) => {
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
