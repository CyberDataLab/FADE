// Angular core and shared modules
import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common'; 
import { FormsModule } from '@angular/forms'; 
import { RouterModule } from '@angular/router';

// Application-specific models and services
import { UserPatch } from '../../DTOs/UserPatch';
import { UserService } from '../../Core/services/user.service';
import { ThemeToggleComponent } from '../../Theme/theme-toggle/theme-toggle.component';

/**
 * @summary Handles sending a password reset email.
 * 
 * This component validates the email field and interacts with the
 * backend to trigger the reset email process.
 */
@Component({
  selector: 'app-send-email',
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    ThemeToggleComponent
  ],
  templateUrl: './send-email.component.html',
  styleUrl: './send-email.component.css'
})
export class SendEmailComponent implements OnInit {

  /** @summary Object bound to the email form field */
  userPatchDTO: UserPatch = {
    username: '',
    old_password: '',
    new_password: '',
    confirm_new_password: '',
    email: ''
  };

  /** @summary Flags for required and pattern validation */
  emailError: boolean;
  badEmailError: boolean;

  /** @summary Regex pattern for validating email format */
  emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/;

  /**
   * @summary Injects required services.
   * 
   * @param userService Service to send reset email
   * @param router Angular router for navigation
   */
  constructor(
    private userService: UserService,
    private router: Router
  ) {
    this.emailError = false;
    this.badEmailError = false;
  }

  /**
   * @summary Initializes the component.
   */
  ngOnInit(): void {}

  /**
   * @summary Validates email input and sends reset email request.
   * 
   * If email is valid, calls the backend to send reset instructions.
   * Navigates to login page on success, alerts on failure.
   */
  sendEmail(): void {
    // Reset validation flags
    this.emailError = false;
    this.badEmailError = false;

    // Validate email field
    if (this.userPatchDTO.email === '') {
      this.emailError = true;
    } else if (!this.emailPattern.test(this.userPatchDTO.email)) {
      this.badEmailError = true;
    }

    // Attempt to send email if validations pass
    if (
      this.userPatchDTO.email !== '' &&
      !this.badEmailError
    ) {
      this.userService.sendEmail(this.userPatchDTO).subscribe(
        () => {
          this.router.navigate(['/login']);
        },
        () => {
          alert("The entered email address is not in the database.");
        }
      );
    }
  }
}
