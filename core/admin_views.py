"""
Custom admin views for Neo4j graph data.
These views render inside the Unfold admin layout.
"""
import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

import logging

from django.urls import reverse

from core.db.queries import (
    bulk_classify_contacts,
    bulk_dismiss_contacts,
    bulk_link_people_to_business,
    classify_contact,
    convert_contact_to_lead,
    create_lead_relationship,
    create_or_merge_business,
    create_or_merge_person,
    create_or_merge_product,
    delete_product,
    dismiss_contact,
    get_all_businesses,
    get_all_contacts,
    get_all_people,
    get_all_products,
    get_analytics_summary,
    get_business_by_id,
    get_contact_source_apps,
    get_contacts_count,
    get_imported_people,
    get_imported_people_count,
    get_leads,
    get_people_by_business,
    get_person_with_connections,
    get_product_with_leads,
    link_person_to_business,
    update_lead_stage,
    update_product,
    IMPORT_SOURCES,
)
from core.graph.queries import get_graph_snapshot
from core.importers.file_parser import parse_import_file

logger = logging.getLogger(__name__)


class Neo4jAdminMixin:
    """Shared context for all Neo4j admin views."""

    def get_admin_context(self, request, title):
        from django.contrib import admin as django_admin

        # Use each_context() to get the full Unfold context (theme, styles,
        # scripts, sidebar, environment badge, etc.)
        context = django_admin.site.each_context(request)
        context.update({
            "title": title,
            "has_permission": request.user.is_staff,
            "is_popup": False,
            "is_nav_sidebar_enabled": True,
            "available_apps": django_admin.site.get_app_list(request),
        })
        return context


@method_decorator(staff_member_required, name="dispatch")
class PeopleListView(Neo4jAdminMixin, View):
    """List all people from Neo4j."""

    def get(self, request):
        page = int(request.GET.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        search = request.GET.get("q", "").strip()

        people = get_all_people(limit=per_page, offset=offset)

        if search:
            search_lower = search.lower()
            people = [
                p for p in people
                if search_lower in (p.get("name") or "").lower()
                or search_lower in (p.get("email") or "").lower()
            ]

        context = self.get_admin_context(request, "People")
        context.update({
            "people": people,
            "search_query": search,
            "page": page,
            "per_page": per_page,
            "has_next": len(people) == per_page,
            "has_prev": page > 1,
        })
        return render(request, "admin/neo4j/people_list.html", context)

    def post(self, request):
        data = {
            "name": request.POST.get("name", "").strip(),
            "email": request.POST.get("email", "").strip(),
            "title": request.POST.get("title", "").strip() or None,
            "linkedin_url": request.POST.get("linkedin_url", "").strip() or None,
            "location": request.POST.get("location", "").strip() or None,
            "source": request.POST.get("source", "").strip() or "admin",
        }
        if not data["name"] or not data["email"]:
            messages.error(request, "Name and email are required.")
            return redirect("admin-neo4j-people")
        try:
            create_or_merge_person(data)
            messages.success(request, f"Person \"{data['name']}\" added successfully.")
        except Exception as e:
            messages.error(request, f"Failed to add person: {e}")
        return redirect("admin-neo4j-people")


@method_decorator(staff_member_required, name="dispatch")
class PersonDetailView(Neo4jAdminMixin, View):
    """Detail view for a single person from Neo4j."""

    def get(self, request, person_id):
        person = get_person_with_connections(person_id)
        if not person:
            from django.http import Http404
            raise Http404("Person not found in Neo4j")

        context = self.get_admin_context(request, f"Person: {person.get('name', person_id)}")
        context["person"] = person
        # Parse AI tags if stored as JSON string
        ai_tags = person.get("ai_tags")
        if isinstance(ai_tags, str):
            try:
                ai_tags = json.loads(ai_tags)
            except (json.JSONDecodeError, TypeError):
                ai_tags = []
        context["ai_tags_parsed"] = ai_tags or []
        # Pass all businesses for the "Link to Business" dropdown
        context["all_businesses"] = get_all_businesses(limit=500)
        # Pass all products for the "Convert to Lead" searchable select
        context["all_products"] = get_all_products(limit=500)
        return render(request, "admin/neo4j/person_detail.html", context)

    def post(self, request, person_id):
        action = request.POST.get("action", "")

        if action == "link_business":
            business_id = request.POST.get("business_id", "").strip()
            if not business_id:
                messages.error(request, "Please select a business.")
                return redirect("admin-neo4j-person-detail", person_id=person_id)
            try:
                link_person_to_business(person_id, business_id)
                business = get_business_by_id(business_id)
                biz_name = business.get("name", business_id) if business else business_id
                messages.success(request, f"Successfully linked to \"{biz_name}\".")
            except Exception as e:
                messages.error(request, f"Failed to link to business: {e}")
            return redirect("admin-neo4j-person-detail", person_id=person_id)

        # Default: convert to lead
        product = request.POST.get("product", "").strip()
        stage = request.POST.get("stage", "").strip() or "new"
        score = request.POST.get("score", "").strip()

        if not product:
            messages.error(request, "Product name is required.")
            return redirect("admin-neo4j-person-detail", person_id=person_id)

        try:
            person = get_person_with_connections(person_id)
            score_val = float(score) if score else float(person.get("score", 0))
            create_lead_relationship(person_id, product, stage, score_val)
            messages.success(request, f"Successfully converted to lead for product \"{product}\".")
        except Exception as e:
            messages.error(request, f"Failed to convert to lead: {e}")
        return redirect("admin-neo4j-person-detail", person_id=person_id)


@method_decorator(staff_member_required, name="dispatch")
class BusinessListView(Neo4jAdminMixin, View):
    """List all businesses from Neo4j."""

    def get(self, request):
        page = int(request.GET.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        search = request.GET.get("q", "").strip()

        businesses = get_all_businesses(limit=per_page, offset=offset)

        if search:
            search_lower = search.lower()
            businesses = [
                b for b in businesses
                if search_lower in (b.get("name") or "").lower()
                or search_lower in (b.get("industry") or "").lower()
            ]

        context = self.get_admin_context(request, "Businesses")
        context.update({
            "businesses": businesses,
            "search_query": search,
            "page": page,
            "per_page": per_page,
            "has_next": len(businesses) == per_page,
            "has_prev": page > 1,
        })
        return render(request, "admin/neo4j/business_list.html", context)

    def post(self, request):
        data = {
            "name": request.POST.get("name", "").strip(),
            "industry": request.POST.get("industry", "").strip() or None,
            "size": request.POST.get("size", "").strip() or None,
            "website": request.POST.get("website", "").strip() or None,
            "location": request.POST.get("location", "").strip() or None,
        }
        if not data["name"]:
            messages.error(request, "Business name is required.")
            return redirect("admin-neo4j-businesses")
        try:
            create_or_merge_business(data)
            messages.success(request, f"Business \"{data['name']}\" added successfully.")
        except Exception as e:
            messages.error(request, f"Failed to add business: {e}")
        return redirect("admin-neo4j-businesses")


@method_decorator(staff_member_required, name="dispatch")
class LeadListView(Neo4jAdminMixin, View):
    """List all leads from Neo4j."""

    def get(self, request):
        stage = request.GET.get("stage", "")
        product = request.GET.get("product", "")
        persona = request.GET.get("persona", "")

        kwargs = {}
        if stage:
            kwargs["stage"] = stage
        if product:
            kwargs["product"] = product
        if persona:
            kwargs["ai_persona"] = persona

        leads = get_leads(**kwargs)

        context = self.get_admin_context(request, "Leads")
        context.update({
            "leads": leads,
            "filter_stage": stage,
            "filter_product": product,
            "filter_persona": persona,
        })
        return render(request, "admin/neo4j/lead_list.html", context)


@method_decorator(staff_member_required, name="dispatch")
class GraphExplorerView(Neo4jAdminMixin, View):
    """Interactive graph snapshot view."""

    def get(self, request):
        context = self.get_admin_context(request, "Graph Explorer")
        return render(request, "admin/neo4j/graph_explorer.html", context)


@method_decorator(staff_member_required, name="dispatch")
class BusinessDetailView(Neo4jAdminMixin, View):
    """Detail view for a single business with linked people and lead conversion."""

    def get(self, request, business_id):
        business = get_business_by_id(business_id)
        if not business:
            from django.http import Http404
            raise Http404("Business not found in Neo4j")

        people = get_people_by_business(business_id)
        linked_ids = {p.get("id") for p in people}
        all_people = get_all_people(limit=500)
        unlinked_people = [p for p in all_people if p.get("id") not in linked_ids]

        context = self.get_admin_context(request, f"Business: {business.get('name', business_id)}")
        context.update({
            "business": business,
            "people": people,
            "unlinked_people": unlinked_people,
            "all_products": get_all_products(limit=500),
        })
        return render(request, "admin/neo4j/business_detail.html", context)

    def post(self, request, business_id):
        action = request.POST.get("action", "")

        if action == "add_person":
            person_id = request.POST.get("person_id", "").strip()
            if not person_id:
                messages.error(request, "Please select a person.")
                return redirect("admin-neo4j-business-detail", business_id=business_id)
            try:
                link_person_to_business(person_id, business_id)
                person = get_person_with_connections(person_id)
                person_name = person.get("name", person_id) if person else person_id
                messages.success(request, f"Successfully linked \"{person_name}\" to this business.")
            except Exception as e:
                messages.error(request, f"Failed to link person: {e}")
            return redirect("admin-neo4j-business-detail", business_id=business_id)

        # Default: convert to lead
        product = request.POST.get("product", "").strip()
        stage = request.POST.get("stage", "").strip() or "new"
        score = request.POST.get("score", "").strip()
        person_ids = request.POST.getlist("person_ids")

        if not product:
            messages.error(request, "Product name is required.")
            return redirect("admin-neo4j-business-detail", business_id=business_id)

        if not person_ids:
            messages.error(request, "Please select at least one person to convert.")
            return redirect("admin-neo4j-business-detail", business_id=business_id)

        try:
            score_val = float(score) if score else 0.0
            count = 0
            for pid in person_ids:
                create_lead_relationship(pid, product, stage, score_val)
                count += 1
            messages.success(request, f"Successfully converted {count} {'person' if count == 1 else 'people'} to leads for \"{product}\".")
        except Exception as e:
            messages.error(request, f"Failed to convert to leads: {e}")
        return redirect("admin-neo4j-business-detail", business_id=business_id)


@method_decorator(staff_member_required, name="dispatch")
class ProductListView(Neo4jAdminMixin, View):
    """List all products from Neo4j."""

    def get(self, request):
        page = int(request.GET.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        search = request.GET.get("q", "").strip()

        products = get_all_products(limit=per_page, offset=offset)

        if search:
            search_lower = search.lower()
            products = [
                p for p in products
                if search_lower in (p.get("name") or "").lower()
                or search_lower in (p.get("description") or "").lower()
            ]

        context = self.get_admin_context(request, "Products")
        context.update({
            "products": products,
            "search_query": search,
            "page": page,
            "per_page": per_page,
            "has_next": len(products) == per_page,
            "has_prev": page > 1,
        })
        return render(request, "admin/neo4j/product_list.html", context)

    def post(self, request):
        data = {
            "name": request.POST.get("name", "").strip(),
            "url": request.POST.get("url", "").strip() or None,
            "description": request.POST.get("description", "").strip() or None,
        }
        if not data["name"]:
            messages.error(request, "Product name is required.")
            return redirect("admin-neo4j-products")
        try:
            create_or_merge_product(data)
            messages.success(request, f"Product \"{data['name']}\" added successfully.")
        except Exception as e:
            messages.error(request, f"Failed to add product: {e}")
        return redirect("admin-neo4j-products")


@method_decorator(staff_member_required, name="dispatch")
class ProductDetailView(Neo4jAdminMixin, View):
    """Detail view for a single product with linked leads."""

    def get(self, request, product_id):
        product = get_product_with_leads(product_id)
        if not product:
            from django.http import Http404
            raise Http404("Product not found in Neo4j")

        context = self.get_admin_context(request, f"Product: {product.get('name', product_id)}")
        context["product"] = product
        return render(request, "admin/neo4j/product_detail.html", context)

    def post(self, request, product_id):
        action = request.POST.get("action", "")

        if action == "edit_product":
            data = {
                "url": request.POST.get("url", "").strip() or None,
                "description": request.POST.get("description", "").strip() or None,
            }
            try:
                update_product(product_id, data)
                messages.success(request, "Product updated successfully.")
            except Exception as e:
                messages.error(request, f"Failed to update product: {e}")
            return redirect("admin-neo4j-product-detail", product_id=product_id)

        if action == "delete_product":
            try:
                delete_product(product_id)
                messages.success(request, "Product deleted successfully.")
            except Exception as e:
                messages.error(request, f"Failed to delete product: {e}")
                return redirect("admin-neo4j-product-detail", product_id=product_id)
            return redirect("admin-neo4j-products")

        messages.error(request, "Unknown action.")
        return redirect("admin-neo4j-product-detail", product_id=product_id)


@method_decorator(staff_member_required, name="dispatch")
class ContactListView(Neo4jAdminMixin, View):
    """Staging inbox for contacts received via RabbitMQ from external apps."""

    def get(self, request):
        page = int(request.GET.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        search = request.GET.get("q", "").strip()
        status_filter = request.GET.get("status", "").strip()
        type_filter = request.GET.get("type", "").strip()
        source_filter = request.GET.get("source_app", "").strip()

        contacts = get_all_contacts(
            status=status_filter,
            contact_type=type_filter,
            source_app=source_filter,
            search=search,
            limit=per_page,
            offset=offset,
        )
        total = get_contacts_count(
            status=status_filter,
            contact_type=type_filter,
            source_app=source_filter,
            search=search,
        )

        context = self.get_admin_context(request, "Contacts")
        context.update({
            "contacts": contacts,
            "search_query": search,
            "status_filter": status_filter,
            "type_filter": type_filter,
            "source_filter": source_filter,
            "source_apps": get_contact_source_apps(),
            "all_products": get_all_products(limit=500),
            "page": page,
            "per_page": per_page,
            "total": total,
            "has_next": offset + per_page < total,
            "has_prev": page > 1,
        })
        return render(request, "admin/neo4j/contact_list.html", context)

    def post(self, request):
        action = request.POST.get("action", "")

        if action == "classify":
            return self._handle_classify(request)
        elif action == "bulk_classify":
            return self._handle_bulk_classify(request)
        elif action == "convert_lead":
            return self._handle_convert_lead(request)
        elif action == "dismiss":
            return self._handle_dismiss(request)
        elif action == "bulk_dismiss":
            return self._handle_bulk_dismiss(request)

        messages.error(request, "Unknown action.")
        return redirect("admin-neo4j-contacts")

    def _handle_classify(self, request):
        contact_id = request.POST.get("contact_id", "").strip()
        contact_type = request.POST.get("contact_type", "").strip()

        if not contact_id or contact_type not in ("person", "business"):
            messages.error(request, "Contact ID and valid type (person/business) are required.")
            return redirect("admin-neo4j-contacts")

        # Collect override fields from the classify form
        overrides = {}
        for field in ("name", "email", "title", "linkedin_url", "location",
                       "company_name", "company_industry", "company_size", "company_website"):
            val = request.POST.get(field, "").strip()
            if val:
                overrides[field] = val

        try:
            result = classify_contact(contact_id, contact_type, request.user.username, overrides=overrides or None)
            messages.success(
                request,
                f"Contact \"{result.get('name')}\" classified as {contact_type}."
            )
        except Exception as e:
            messages.error(request, f"Failed to classify contact: {e}")
        return redirect("admin-neo4j-contacts")

    def _handle_bulk_classify(self, request):
        contact_ids = request.POST.getlist("selected_ids")
        contact_type = request.POST.get("contact_type", "").strip()

        if not contact_ids:
            messages.error(request, "Please select at least one contact.")
            return redirect("admin-neo4j-contacts")
        if contact_type not in ("person", "business"):
            messages.error(request, "Please select a valid type (person/business).")
            return redirect("admin-neo4j-contacts")

        try:
            count = bulk_classify_contacts(contact_ids, contact_type, request.user.username)
            messages.success(
                request,
                f"Classified {count} contact(s) as {contact_type}."
            )
        except Exception as e:
            messages.error(request, f"Failed to classify contacts: {e}")
        return redirect("admin-neo4j-contacts")

    def _handle_convert_lead(self, request):
        contact_id = request.POST.get("contact_id", "").strip()
        product = request.POST.get("product", "").strip()
        stage = request.POST.get("stage", "").strip() or "New Lead"
        score = request.POST.get("score", "").strip()

        if not contact_id:
            messages.error(request, "Contact ID is required.")
            return redirect("admin-neo4j-contacts")

        try:
            score_val = float(score) if score else 40.0
            result = convert_contact_to_lead(contact_id, product, stage, score_val)
            messages.success(
                request,
                f"Contact \"{result.get('name')}\" converted to lead for \"{product or result.get('source_product', 'General')}\"."
            )
        except Exception as e:
            messages.error(request, f"Failed to convert to lead: {e}")
        return redirect("admin-neo4j-contacts")

    def _handle_dismiss(self, request):
        contact_id = request.POST.get("contact_id", "").strip()
        if not contact_id:
            messages.error(request, "Contact ID is required.")
            return redirect("admin-neo4j-contacts")

        try:
            dismiss_contact(contact_id)
            messages.success(request, "Contact dismissed.")
        except Exception as e:
            messages.error(request, f"Failed to dismiss contact: {e}")
        return redirect("admin-neo4j-contacts")

    def _handle_bulk_dismiss(self, request):
        contact_ids = request.POST.getlist("selected_ids")
        if not contact_ids:
            messages.error(request, "Please select at least one contact.")
            return redirect("admin-neo4j-contacts")

        try:
            bulk_dismiss_contacts(contact_ids)
            messages.success(request, f"Dismissed {len(contact_ids)} contact(s).")
        except Exception as e:
            messages.error(request, f"Failed to dismiss contacts: {e}")
        return redirect("admin-neo4j-contacts")


SOURCE_FILTER_MAP = {
    "linkedin": ["apify_linkedin"],
    "csv": ["csv_import"],
    "xlsx": ["xlsx_import"],
    "api": ["api_external"],
}


@method_decorator(staff_member_required, name="dispatch")
class ImportListView(Neo4jAdminMixin, View):
    """Import contacts: LinkedIn scrape, CSV/XLSX upload, and imported contacts list."""

    def get(self, request):
        page = int(request.GET.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        search = request.GET.get("q", "").strip()
        source_filter = request.GET.get("source", "").strip()

        sources = SOURCE_FILTER_MAP.get(source_filter, IMPORT_SOURCES)

        people = get_imported_people(sources=sources, limit=per_page, offset=offset, search=search)
        total = get_imported_people_count(sources=sources, search=search)

        preview_rows = request.session.get("import_preview_rows")
        preview_errors = request.session.get("import_preview_errors")
        preview_filename = request.session.get("import_preview_filename")

        context = self.get_admin_context(request, "Import Contacts")
        context.update({
            "people": people,
            "search_query": search,
            "source_filter": source_filter,
            "page": page,
            "per_page": per_page,
            "total": total,
            "has_next": offset + per_page < total,
            "has_prev": page > 1,
            "all_businesses": get_all_businesses(limit=500),
            "all_products": get_all_products(limit=500),
            "preview_rows": preview_rows,
            "preview_errors": preview_errors,
            "preview_filename": preview_filename,
        })
        return render(request, "admin/neo4j/import_list.html", context)

    def post(self, request):
        action = request.POST.get("action", "")

        if action == "linkedin_scrape":
            return self._handle_linkedin_scrape(request)
        elif action == "file_preview":
            return self._handle_file_preview(request)
        elif action == "file_confirm":
            return self._handle_file_confirm(request)
        elif action == "cancel_preview":
            request.session.pop("import_preview_rows", None)
            request.session.pop("import_preview_errors", None)
            request.session.pop("import_preview_filename", None)
            return redirect("admin-neo4j-imports")
        elif action == "link_business":
            return self._handle_link_business(request)
        elif action == "convert_lead":
            return self._handle_convert_lead(request)

        messages.error(request, "Unknown action.")
        return redirect("admin-neo4j-imports")

    def _handle_linkedin_scrape(self, request):
        linkedin_url = request.POST.get("linkedin_url", "").strip()
        product = request.POST.get("product", "").strip()

        if not linkedin_url:
            messages.error(request, "LinkedIn URL is required.")
            return redirect("admin-neo4j-imports")

        try:
            from integrations.apify.scraper import ApifyScraper
            webhook_url = request.build_absolute_uri(reverse("apify-webhook"))
            scraper = ApifyScraper()
            run_id = scraper.start_linkedin_scrape(linkedin_url, product or "General", webhook_url)
            messages.success(
                request,
                f"LinkedIn scrape started (run ID: {run_id}). "
                f"Results will appear here once scraping completes."
            )
        except Exception as e:
            messages.error(request, f"Failed to start LinkedIn scrape: {e}")
        return redirect("admin-neo4j-imports")

    def _handle_file_preview(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("admin-neo4j-imports")

        if uploaded_file.size > 5 * 1024 * 1024:
            messages.error(request, "File too large. Maximum size is 5 MB.")
            return redirect("admin-neo4j-imports")

        try:
            valid_rows, errors = parse_import_file(uploaded_file, uploaded_file.name)
        except Exception as e:
            messages.error(request, f"Failed to parse file: {e}")
            return redirect("admin-neo4j-imports")

        if not valid_rows and errors:
            for err in errors:
                messages.error(request, err)
            return redirect("admin-neo4j-imports")

        # Store preview in session (cap at 500 rows)
        request.session["import_preview_rows"] = valid_rows[:500]
        request.session["import_preview_errors"] = errors
        request.session["import_preview_filename"] = uploaded_file.name

        if len(valid_rows) > 500:
            messages.warning(request, f"Showing first 500 of {len(valid_rows)} rows.")
        if errors:
            messages.warning(request, f"{len(errors)} row(s) had validation errors and will be skipped.")

        messages.success(request, f"{len(valid_rows)} valid contact(s) ready to import.")
        return redirect("admin-neo4j-imports")

    def _handle_file_confirm(self, request):
        rows = request.session.pop("import_preview_rows", None)
        request.session.pop("import_preview_errors", None)
        request.session.pop("import_preview_filename", None)

        if not rows:
            messages.error(request, "No import data found. Please upload a file first.")
            return redirect("admin-neo4j-imports")

        created = 0
        linked = 0
        for row in rows:
            company_name = row.pop("company", None)
            try:
                person_id = create_or_merge_person(row)
                created += 1
                if company_name:
                    biz_id = create_or_merge_business({"name": company_name})
                    link_person_to_business(person_id, biz_id)
                    linked += 1
            except Exception as e:
                logger.error("Import row failed: %s — %s", row.get("email"), e)

        msg = f"Successfully imported {created} contact(s)."
        if linked:
            msg += f" Linked {linked} to businesses."
        messages.success(request, msg)
        return redirect("admin-neo4j-imports")

    def _handle_link_business(self, request):
        person_ids = request.POST.getlist("selected_ids")
        business_id = request.POST.get("business_id", "").strip()

        if not person_ids:
            messages.error(request, "Please select at least one contact.")
            return redirect("admin-neo4j-imports")
        if not business_id:
            messages.error(request, "Please select a business.")
            return redirect("admin-neo4j-imports")

        try:
            bulk_link_people_to_business(person_ids, business_id)
            biz = get_business_by_id(business_id)
            biz_name = biz.get("name", business_id) if biz else business_id
            messages.success(
                request,
                f"Linked {len(person_ids)} contact(s) to \"{biz_name}\"."
            )
        except Exception as e:
            messages.error(request, f"Failed to link contacts: {e}")
        return redirect("admin-neo4j-imports")

    def _handle_convert_lead(self, request):
        person_ids = request.POST.getlist("selected_ids")
        product = request.POST.get("product", "").strip()
        stage = request.POST.get("stage", "").strip() or "new"
        score = request.POST.get("score", "").strip()

        if not person_ids:
            messages.error(request, "Please select at least one contact.")
            return redirect("admin-neo4j-imports")
        if not product:
            messages.error(request, "Product name is required.")
            return redirect("admin-neo4j-imports")

        try:
            score_val = float(score) if score else 0.0
            for pid in person_ids:
                create_lead_relationship(pid, product, stage, score_val)
            messages.success(
                request,
                f"Converted {len(person_ids)} contact(s) to leads for \"{product}\"."
            )
        except Exception as e:
            messages.error(request, f"Failed to convert to leads: {e}")
        return redirect("admin-neo4j-imports")


@method_decorator(staff_member_required, name="dispatch")
class GraphSnapshotAPIView(View):
    """JSON endpoint for graph data (used by the explorer)."""

    def get(self, request):
        try:
            snapshot = get_graph_snapshot()
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
        return JsonResponse(snapshot)


VALID_STAGES = {"new", "contacted", "qualified", "proposal", "negotiation", "won", "lost"}


@method_decorator(staff_member_required, name="dispatch")
class PipelineView(Neo4jAdminMixin, View):
    """Kanban-style pipeline board for leads."""

    def get(self, request):
        context = self.get_admin_context(request, "Sales Pipeline")
        context.update({
            "filter_product": request.GET.get("product", ""),
            "filter_persona": request.GET.get("persona", ""),
        })
        return render(request, "admin/neo4j/pipeline.html", context)


@method_decorator(staff_member_required, name="dispatch")
class PipelineLeadsAPIView(View):
    """JSON endpoint for fetching leads (used by pipeline board)."""

    def get(self, request):
        kwargs = {}
        product = request.GET.get("product", "")
        persona = request.GET.get("persona", "")
        if product:
            kwargs["product"] = product
        if persona:
            kwargs["ai_persona"] = persona
        try:
            leads = get_leads(**kwargs, limit=500)
            return JsonResponse({"leads": leads})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(staff_member_required, name="dispatch")
class PipelineStageUpdateView(View):
    """JSON endpoint for updating lead stage from pipeline board."""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        person_id = data.get("person_id")
        new_stage = data.get("stage")

        if not person_id or not new_stage:
            return JsonResponse({"error": "person_id and stage are required"}, status=400)

        if new_stage not in VALID_STAGES:
            return JsonResponse({"error": f"Invalid stage: {new_stage}"}, status=400)

        try:
            updated = update_lead_stage(person_id, new_stage)
            if updated == 0:
                return JsonResponse({"error": "Lead not found"}, status=404)
            return JsonResponse({"person_id": person_id, "stage": new_stage})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
