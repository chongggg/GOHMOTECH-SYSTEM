"""
Management command to test email notifications.
Usage: python manage.py test_email_notification
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = 'Send a test email notification'

    def add_arguments(self, parser):
        parser.add_argument(
            '--recipient',
            type=str,
            default=None,
            help='Email recipient (default: ADMIN_EMAIL from settings)'
        )
        parser.add_argument(
            '--recipients',
            type=str,
            default=None,
            help='Multiple recipients separated by comma (e.g., "email1@gmail.com,email2@gmail.com")'
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("📧 Email Notification Test")
        self.stdout.write("=" * 60)
        self.stdout.write("")
        
        # Get recipients
        recipients = []
        if options['recipients']:
            # Multiple recipients separated by comma
            recipients = [email.strip() for email in options['recipients'].split(',')]
        elif options['recipient']:
            # Single recipient
            recipients = [options['recipient']]
        elif settings.ADMIN_EMAIL:
            # Default to ADMIN_EMAIL
            recipients = [settings.ADMIN_EMAIL]
        else:
            self.stdout.write(self.style.ERROR("❌ No recipient email configured!"))
            self.stdout.write("")
            self.stdout.write("Please set ADMIN_EMAIL in your .env file or use --recipient/--recipients option")
            self.stdout.write("")
            self.stdout.write("Examples:")
            self.stdout.write("  Single: python manage.py test_email_notification --recipient your@email.com")
            self.stdout.write("  Multiple: python manage.py test_email_notification --recipients \"email1@gmail.com,email2@gmail.com\"")
            return
        
        # Check email configuration
        self.stdout.write("📋 Configuration:")
        self.stdout.write(f"   Email Backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"   Email Host: {settings.EMAIL_HOST}")
        self.stdout.write(f"   Email Port: {settings.EMAIL_PORT}")
        self.stdout.write(f"   Email User: {settings.EMAIL_HOST_USER or '(not set)'}")
        self.stdout.write(f"   Recipients ({len(recipients)}):")
        for i, recipient in enumerate(recipients, 1):
            self.stdout.write(f"      {i}. {recipient}")
        self.stdout.write("")
        
        # Prepare test email
        subject = "🐐 Test Email - Goat Monitoring System"
        message = f"""
Test Email from Goat Monitoring System
========================================

This is a test email to verify that email notifications are working correctly.

System Information:
- Test Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
- Email Backend: {settings.EMAIL_BACKEND}
- Email Host: {settings.EMAIL_HOST}

If you receive this email, your email configuration is working!

Next Steps:
1. ✅ Email is configured correctly
2. The system can now send alerts for:
   - Missing goat alerts
   - New goat detections
   - Door automation status
   - System notifications

---
Smart Goat Monitoring System
Automated Livestock Management
        """.strip()
        
        from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
        
        self.stdout.write("📤 Sending test email...")
        self.stdout.write("")
        
        try:
            # Send email to all recipients
            result = send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipients,
                fail_silently=False,
            )
            
            if result >= 1:
                self.stdout.write(self.style.SUCCESS(f"✅ Email sent successfully to {len(recipients)} recipient(s)!"))
                self.stdout.write("")
                self.stdout.write("📬 Check inboxes:")
                for recipient in recipients:
                    self.stdout.write(f"   - {recipient}")
                self.stdout.write("")
                self.stdout.write("💡 Tips:")
                self.stdout.write("   - Check spam folder if not in inbox")
                self.stdout.write("   - Gmail: Check 'All Mail' folder")
                self.stdout.write("   - May take 1-30 seconds to arrive")
                self.stdout.write("")
                
                # Test with NotificationService
                self.stdout.write("🔄 Testing NotificationService...")
                try:
                    from iot.notification_service import get_notification_service
                    service = get_notification_service()
                    
                    # Send test notification through service to all recipients
                    success_count = 0
                    for recipient in recipients:
                        test_result = service._send_email(
                            subject="🐐 Test via NotificationService",
                            message="This email was sent through the NotificationService class.",
                            recipient=recipient
                        )
                        if test_result:
                            success_count += 1
                    
                    if success_count == len(recipients):
                        self.stdout.write(self.style.SUCCESS(f"✅ NotificationService emails sent to all {len(recipients)} recipients!"))
                    elif success_count > 0:
                        self.stdout.write(self.style.WARNING(f"⚠️  NotificationService sent to {success_count}/{len(recipients)} recipients"))
                    else:
                        self.stdout.write(self.style.WARNING("⚠️  NotificationService emails may have failed"))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ NotificationService test failed: {e}"))
                
            else:
                self.stdout.write(self.style.ERROR("❌ Email sending failed (result = 0)"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error sending email: {e}"))
            self.stdout.write("")
            self.stdout.write("Common issues:")
            self.stdout.write("")
            self.stdout.write("1. Gmail App Password:")
            self.stdout.write("   - Don't use your Gmail password directly")
            self.stdout.write("   - Generate App Password: Google Account → Security → 2FA → App Passwords")
            self.stdout.write("")
            self.stdout.write("2. Environment Variables:")
            self.stdout.write("   - EMAIL_HOST_USER=your-email@gmail.com")
            self.stdout.write("   - EMAIL_HOST_PASSWORD=your-app-password")
            self.stdout.write("   - ADMIN_EMAIL=recipient@email.com")
            self.stdout.write("")
            self.stdout.write("3. SMTP Settings:")
            self.stdout.write("   - Gmail: smtp.gmail.com:587")
            self.stdout.write("   - Outlook: smtp-mail.outlook.com:587")
            self.stdout.write("")
            self.stdout.write("4. For Testing (Console Output):")
            self.stdout.write("   In settings.py, use:")
            self.stdout.write("   EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'")
            self.stdout.write("")
        
        self.stdout.write("=" * 60)
